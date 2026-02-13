import time

from textual import work
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import ListView, ListItem, Static, Footer

from rikka import CSS_PATH
from ..backend.backend import AnimeBackend
from rikka.utils.logger import get_logger

class EpisodeDetailScreen(Screen):
    BINDINGS = [
        ("escape", "go_back", "Go Back"),
    ]
    CSS_PATH = CSS_PATH / "episode_styles.css"

    def __init__(self, anime, backend: AnimeBackend, **kwargs):
        super().__init__(**kwargs)
        self.anime = anime
        self.backend = backend
        self.episodes = []
        self.logger = get_logger("EpisodeScreen")

    def compose(self) -> ComposeResult:
        yield Static(self.anime.name, id="title")
        yield ListView(id="episode_list")
        yield Static('', id='loading_display')
        yield Footer()

    def on_mount(self):
        self.load_episodes()

    @work(thread=True, exclusive=True, name='EpisodesWorker')
    def load_episodes(self):
        self.app.call_from_thread(self._set_loading_text, "Loading episodes... :3")

        episode_list = self.query_one("#episode_list", ListView)
        self.app.call_from_thread(episode_list.clear)

        self.episodes = self.backend.get_episodes(self.anime)

        if not self.episodes:
            self.app.call_from_thread(
                episode_list.append,
                ListItem(Static("No episodes found :("))
            )
            self.app.call_from_thread(self._set_loading_text, "")
            return

        for idx, ep_num in enumerate(self.episodes):
            label = f"Ep {ep_num}"
            item = ListItem(Static(label))
            item.episode_number = ep_num
            self.app.call_from_thread(episode_list.append, item)
            time.sleep(0.001)

        self.app.call_from_thread(self._set_loading_text, "")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle when a user clicks or presses enter on an episode"""
        selected_item = event.item
        episode_number = getattr(selected_item, "episode_number", None)
        if episode_number is None:
            return

        self.fetch_and_play(episode_number)

    @work(thread=True)
    def fetch_and_play(self, episode_number):
        self.app.call_from_thread(
            self._set_loading_text,
            f"Loading episode {episode_number}... :3"
        )

        stream = self.backend.get_episode_stream(
            self.anime,
            episode_number,
            self.backend.global_quality
        )

        if not stream:
            self.app.call_from_thread(
                self.app.notify,
                "No stream available for this episode :(",
                severity="error",
                timeout=3
            )
            self.app.call_from_thread(self._set_loading_text, "")
            return

        anime_id = getattr(self.anime, "identifier", None)
        if not anime_id:
            self.app.call_from_thread(
                self.app.notify,
                "Anime has no identifier :/",
                severity="error"
            )
            self.app.call_from_thread(self._set_loading_text, "")
            return

        entry = self.backend.watch_history.get_entry(anime_id)
        start_time = 0
        if entry and entry["episode"] == episode_number:
            start_time = entry["timestamp"]

        self.app.call_from_thread(self._set_loading_text, "")
        self.app.call_from_thread(
            self.backend.play_episode,
            self.anime,
            episode_number,
            stream,
            start_time
        )

    def _set_loading_text(self, text: str):
        self.query_one('#loading_display', Static).update(text)

    def action_go_back(self):
        self.app.pop_screen()