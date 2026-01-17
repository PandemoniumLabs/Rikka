from typing import Optional

from .utils import get_referrer_for_url
from .mpv_control import MPVControl
from ..logs.logger import get_logger
from .watch_history import WatchHistory
from .settings_control import AnimeSettings

from anipy_api.anime import Anime
from anipy_api.provider import ProviderStream, LanguageTypeEnum
from anipy_api.provider.providers.allanime_provider import AllAnimeProvider

class AnimeBackend:
    def __init__(self, settings: AnimeSettings = None):
        self.logger = get_logger("AnimeBackend")
        self.provider = AllAnimeProvider()
        self.cache = {}
        self.episodes_cache = {}
        self.watch_history = WatchHistory()
        self.player = MPVControl()
        self.current_anime = None
        self.current_episode = None

        self.settings = settings or AnimeSettings()
        s = self.settings
        self.global_quality = s.get("quality")
        self.auto_resume = s.get("auto_resume")
        self.fullscreen = s.get("fullscreen")
        self.skip_intro_seconds = s.get("skip_intro_seconds")
        self.skip_outro_seconds = s.get("skip_outro_seconds")
        self.auto_next_episode = s.get("auto_next_episode")
        self.save_progress_interval = s.get("save_progress_interval")
        self.minimal_progress_threshold = s.get("minimal_progress_threshold")
        self.history_limit = s.get("history_limit")

        self.logger.debug(f"AnimeBackend ready with settings: {s.get_all()}")

    def get_anime_by_query(self, query):
        """Search for anime by query string. Returns a list of Anime objects"""
        self.logger.info(f"Searching for: {query} :]")
        try:
            results = self.provider.get_search(query)
        except Exception as e:
            self.logger.exception(f"Error during search: {str(e)} :/")
            return []

        if not results:
            self.logger.warning("No results found :(")
            return []

        anime_list = []
        for r in results:
            anime = Anime.from_search_result(self.provider, r)
            anime_id = getattr(anime, "identifier", None)

            if anime_id:
                cached_anime = self.cache.get(anime_id)
                if cached_anime:
                    anime = cached_anime
                else:
                    self.cache[anime_id] = anime
            anime_list.append(anime)

        return anime_list

    def get_episode_stream(self, anime, episode, quality) -> Optional[ProviderStream]:
        """
        Return a single ProviderStream (best matching quality) or None.
        Accepts provider returning either a single ProviderStream or a list.
        """
        try:
            stream = anime.get_video(
                episode=episode, lang=LanguageTypeEnum.SUB, preferred_quality=quality
            )
            self.logger.info(f"stream fetched: {stream} :]")
            if not stream:
                return None

            return stream

        except Exception as e:
            self.logger.exception(f"Error fetching stream: {str(e)} :/")
        return None

    def get_episodes(self, anime):
        """Get a list of episodes for anime, with caching."""
        anime_id = anime.identifier

        if anime_id in self.episodes_cache:
            return self.episodes_cache[anime_id]

        try:
            episodes = anime.get_episodes(lang=self.settings.get("language", LanguageTypeEnum.SUB))
            self.episodes_cache[anime_id] = episodes
            return episodes

        except Exception as e:
            self.logger.exception(f"Error fetching episodes for {anime.name}: {e}")
            return []

    def play_episode(self, anime: Anime, episode: int, stream: ProviderStream, start_time: int = 0):
        """Play a specific episode using MPVPlayer with user-configurable settings."""
        url = stream.url
        anime_id = getattr(anime, "identifier", str(id(anime)))
        anime_name = getattr(anime, "name", "Unknown")
        self.current_anime = anime
        self.current_episode = episode

        start_time += self.skip_intro_seconds
        referrer = getattr(stream, "referrer", None) or get_referrer_for_url(url)

        extra_args = []
        if self.fullscreen:
            extra_args.append("-fs")
        extra_args.append(f"--referrer={referrer}")

        self.logger.info(
            f"Playing {anime_name} EP{episode} with referrer: {referrer}, "
            f"start_time: {start_time}"
        )

        def on_mpv_exit():
            """Called when MPV closes, save watch history"""
            self.logger.info(
                f"MPV closed, saving history for {anime_name} EP:{episode} :)"
            )
            try:
                elapsed = self.player.get_elapsed_time()
                duration = self.player.current_duration or (elapsed + 300)
                self.watch_history.update_progress(
                    anime_id, anime_name, episode, elapsed, duration
                )

                if self.auto_next_episode:
                    next_ep = episode + 1
                    episodes = self.get_episodes(anime)

                    if next_ep <= len(episodes):
                        next_stream = self.get_episode_stream(
                            anime, next_ep, self.global_quality
                        )
                        if next_stream:
                            self.logger.info(
                                f"Auto-playing next episode: EP{next_ep} :3"
                            )
                            self.play_episode(anime, next_ep, next_stream)

            except Exception as e:
                self.logger.debug(f"Failed to save final progress: {e} :/")

        self.player.on_exit = on_mpv_exit
        self.player.launch(url, start_time=start_time, extra_args=extra_args)

        self.player.start_progress_tracker(
            lambda elapsed, duration: self.watch_history.update_progress(
                anime_id, anime_name, episode, elapsed, duration
            ),
            interval=self.save_progress_interval,
        )

    def resume_anime(self, anime_id, quality: int = None):
        """Resume anime playback from watch history, using user settings."""
        quality = quality or self.global_quality
        entry = self.watch_history.get_entry(anime_id)

        if not entry:
            self.logger.warning(f"No history found for anime_id {anime_id} :(")
            return False

        anime = (
            self.cache.get(anime_id)
            or (self.get_anime_by_query(entry["anime_name"]) or [None])[0]
        )
        if not anime:
            self.logger.error("Could not find anime to resume :/")
            return False

        lang = LanguageTypeEnum.SUB
        try:
            stream = anime.get_video(
                episode=entry["episode"], lang=lang, preferred_quality=quality
            )

        except Exception as e:
            self.logger.exception(f"Error fetching stream for resume: {e}")
            return False

        if not stream:
            self.logger.warning("No stream available to resume")
            return False

        start_time = entry.get("timestamp", 0)
        self.play_episode(anime, entry["episode"], stream, start_time=start_time)
        return True

    def get_continue_watching_list(self, limit=10):
        cont = self.watch_history.get_continue_watching(limit)
        result = []

        for anime_id, h in cont:
            result.append(
                {
                    "anime_id": anime_id,
                    "anime_name": h["anime_name"],
                    "episode": h["episode"],
                    "progress_percent": h["progress_percent"],
                    "timestamp": h["timestamp"],
                    "last_watched": h["last_watched"],
                }
            )
        return result

    def _on_play_start(self, anime):
        self.logger.info(f"Playback started: {anime}")
