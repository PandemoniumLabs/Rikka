# File: tests/test_backend_v3.py
# language: python
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ibuki.backend import backend_v3 as backend_mod
from ibuki.backend import settings_control as settings_mod


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def backend(tmp_path):
    """Create a backend instance with isolated config"""
    cfg = tmp_path / "s.yaml"
    s = settings_mod.AnimeSettings(config_path=cfg, use_yaml=True)
    s.set("quality", 720, save=True)
    s.set("skip_intro_seconds", 5, save=True)
    s.set("fullscreen", False, save=True)
    s.set("auto_next_episode", False, save=True)
    s.set("save_progress_interval", 1, save=True)

    b = backend_mod.AnimeBackend(settings=s)
    return b


@pytest.fixture
def mock_anime():
    """Fake anime object with common methods"""
    anime = Mock()
    anime.id = "test_anime_123"
    anime.identifier = "test_anime_123"
    anime.name = "Test Anime"
    anime.get_episodes = Mock(return_value=list(range(1, 13)))
    return anime


@pytest.fixture
def mock_stream():
    """Fake stream object"""
    stream = Mock()
    stream.url = "https://cdn.example.com/video.m3u8"
    stream.referrer = None
    return stream


# ============================================================================
# REFERRER TESTS
# ============================================================================

class TestReferrerLogic:
    def test_fast4speed_domains_use_allanime(self):
        assert backend_mod.AnimeBackend.get_referrer_for_url(
            "https://fast4speed.example/video"
        ) == "https://allanime.day"

        assert backend_mod.AnimeBackend.get_referrer_for_url(
            "https://subdomain.fast4speed.com/ep1"
        ) == "https://allanime.day"

    def test_sunshinerays_domains_use_allmanga(self):
        assert backend_mod.AnimeBackend.get_referrer_for_url(
            "https://sunshinerays.example/foo"
        ) == "https://allmanga.to"

    def test_unknown_domains_default_to_allanime(self):
        assert backend_mod.AnimeBackend.get_referrer_for_url(
            "https://random-cdn.net/video"
        ) == "https://allanime.day"

    def test_empty_url_defaults_safely(self):
        assert backend_mod.AnimeBackend.get_referrer_for_url("") == "https://allanime.day"


# ============================================================================
# SEARCH & CACHING TESTS
# ============================================================================

class TestSearchAndCache:
    def test_search_caches_results(self, backend, monkeypatch):
        """Verify search results are cached properly"""
        fake_results = [
            SimpleNamespace(id="anime1", title="Anime 1"),
            SimpleNamespace(id="anime2", title="Anime 2"),
        ]

        call_count = {"count": 0}

        def mock_search(query):
            call_count["count"] += 1
            return fake_results

        backend.provider.get_search = mock_search
        monkeypatch.setattr(
            backend_mod.Anime,
            "from_search_result",
            lambda provider, r: SimpleNamespace(id=r.id, name=r.title)
        )

        # First call
        results1 = backend.get_anime_by_query("test")
        assert len(results1) == 2
        assert call_count["count"] == 1

        # Second call should use cache
        results2 = backend.get_anime_by_query("test")
        assert len(results2) == 2
        assert results1[0].id == results2[0].id
        # Anime objects should be from cache, not re-created
        assert backend.cache["anime1"] is results2[0]

    def test_search_handles_provider_exception(self, backend):
        """Search should return empty list on provider failure"""
        backend.provider.get_search = Mock(side_effect=ConnectionError("API down"))

        results = backend.get_anime_by_query("test")
        assert results == []

    def test_search_handles_empty_results(self, backend):
        """Empty search results should be handled gracefully"""
        backend.provider.get_search = Mock(return_value=[])

        results = backend.get_anime_by_query("nonexistent_anime_12345")
        assert results == []

    def test_concurrent_cache_access(self, backend, monkeypatch):
        """Cache should handle concurrent access without corruption"""
        fake_results = [SimpleNamespace(id=f"anime{i}", title=f"A{i}") for i in range(5)]
        backend.provider.get_search = Mock(return_value=fake_results)

        monkeypatch.setattr(
            backend_mod.Anime,
            "from_search_result",
            lambda provider, r: SimpleNamespace(id=r.id, name=r.title)
        )

        errors = []

        def search_worker():
            try:
                backend.get_anime_by_query("test")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=search_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(backend.cache) >= 5


# ============================================================================
# EPISODE & STREAM TESTS
# ============================================================================

class TestEpisodesAndStreams:
    def test_get_episodes_caches_results(self, backend, mock_anime):
        """Episode lists should be cached"""
        episodes = backend.get_episodes(mock_anime)
        assert len(episodes) == 12

        # Modify mock to return different data
        mock_anime.get_episodes.return_value = list(range(1, 25))

        # Should still return cached version
        episodes2 = backend.get_episodes(mock_anime)
        assert len(episodes2) == 12
        assert mock_anime.get_episodes.call_count == 1

    def test_get_episodes_handles_exception(self, backend, mock_anime):
        """Should return empty list on episode fetch failure"""
        mock_anime.get_episodes.side_effect = TimeoutError("Took too long")

        episodes = backend.get_episodes(mock_anime)
        assert episodes == []

    def test_get_stream_returns_none_on_failure(self, backend, mock_anime):
        """Stream fetch failures should return None gracefully"""
        mock_anime.get_video = Mock(return_value=None)

        stream = backend.get_episode_stream(mock_anime, 1, 720)
        assert stream is None

    def test_get_stream_passes_correct_params(self, backend, mock_anime, mock_stream):
        """Verify quality and language params are passed correctly"""
        mock_anime.get_video = Mock(return_value=mock_stream)

        from anipy_api.provider import LanguageTypeEnum

        backend.get_episode_stream(mock_anime, 5, 1080)

        mock_anime.get_video.assert_called_once()
        call_kwargs = mock_anime.get_video.call_args[1]
        assert call_kwargs["episode"] == 5
        assert call_kwargs["preferred_quality"] == 1080
        assert call_kwargs["lang"] == LanguageTypeEnum.SUB

    def test_get_stream_handles_api_exception(self, backend, mock_anime):
        """API errors during stream fetch should be caught"""
        mock_anime.get_video = Mock(side_effect=ValueError("Invalid episode"))

        stream = backend.get_episode_stream(mock_anime, 999, 720)
        assert stream is None


# ============================================================================
# PLAYBACK TESTS
# ============================================================================

class TestPlayback:
    def test_play_episode_launches_player_correctly(self, backend, mock_anime, mock_stream):
        """Player should be launched with correct parameters"""
        backend.player = Mock()
        backend.player.get_elapsed_time = Mock(return_value=100)
        backend.player.current_duration = 1440

        backend.play_episode(mock_anime, 1, mock_stream, start_time=10)

        backend.player.launch.assert_called_once()
        call_args = backend.player.launch.call_args

        # Check URL
        assert call_args[0][0] == mock_stream.url

        # Check start time includes skip_intro
        assert call_args[1]["start_time"] == 15  # 10 + 5 (skip_intro_seconds)

        # Check referrer in extra_args
        extra_args = call_args[1]["extra_args"]
        assert any("--referrer=" in arg for arg in extra_args)

    def test_play_episode_adds_fullscreen_flag(self, backend, mock_anime, mock_stream):
        """Fullscreen setting should add -fs flag"""
        backend.settings.set("fullscreen", True, save=True)
        backend.fullscreen = True
        backend.player = Mock()

        backend.play_episode(mock_anime, 1, mock_stream)

        extra_args = backend.player.launch.call_args[1]["extra_args"]
        assert "-fs" in extra_args

    def test_play_episode_saves_progress_on_exit(self, backend, mock_anime, mock_stream):
        """Watch history should update when player exits"""
        backend.player = Mock()
        backend.player.get_elapsed_time = Mock(return_value=600)
        backend.player.current_duration = 1440
        backend.watch_history = Mock()

        backend.play_episode(mock_anime, 3, mock_stream)

        # Simulate player exit
        on_exit_callback = backend.player.on_exit
        assert callable(on_exit_callback)

        on_exit_callback()

        backend.watch_history.update_progress.assert_called()
        call_args = backend.watch_history.update_progress.call_args[0]
        assert call_args[0] == mock_anime.identifier
        assert call_args[1] == mock_anime.name
        assert call_args[2] == 3
        assert call_args[3] == 600

    def test_auto_next_episode_triggers(self, backend, mock_anime, mock_stream):
        """Auto-next should play next episode on exit"""
        backend.settings.set("auto_next_episode", True, save=True)
        backend.auto_next_episode = True
        backend.player = Mock()
        backend.player.get_elapsed_time = Mock(return_value=1400)
        backend.player.current_duration = 1440

        # Mock get_episode_stream to return stream for next episode
        backend.get_episode_stream = Mock(return_value=mock_stream)
        backend.get_episodes = Mock(return_value=list(range(1, 13)))

        backend.play_episode(mock_anime, 5, mock_stream)

        # Simulate exit
        backend.player.on_exit()

        # Should have called get_episode_stream for episode 6
        backend.get_episode_stream.assert_called_with(mock_anime, 6, backend.global_quality)

    def test_auto_next_stops_at_last_episode(self, backend, mock_anime, mock_stream):
        """Auto-next should not trigger after last episode"""
        backend.settings.set("auto_next_episode", True, save=True)
        backend.auto_next_episode = True
        backend.player = Mock()
        backend.player.get_elapsed_time = Mock(return_value=1400)
        backend.get_episodes = Mock(return_value=list(range(1, 13)))

        play_calls = []
        original_play = backend.play_episode

        def track_play(*args, **kwargs):
            play_calls.append(args)
            return original_play(*args, **kwargs)

        backend.play_episode = track_play

        # Play last episode
        backend.play_episode(mock_anime, 12, mock_stream)
        backend.player.on_exit()

        # Should only have initial call, no auto-next
        assert len(play_calls) == 1


# ============================================================================
# RESUME & HISTORY TESTS
# ============================================================================

class TestResumeAndHistory:
    def test_resume_returns_false_when_no_history(self, backend):
        """Resume should fail gracefully when no history exists"""
        backend.watch_history = Mock()
        backend.watch_history.get_entry = Mock(return_value=None)

        result = backend.resume_anime("nonexistent_id")
        assert result is False

    def test_resume_loads_from_history(self, backend, mock_anime, mock_stream):
        """Resume should use stored timestamp and episode"""
        history_entry = {
            "anime_name": "Test Anime",
            "episode": 5,
            "timestamp": 300
        }

        backend.watch_history = Mock()
        backend.watch_history.get_entry = Mock(return_value=history_entry)
        backend.cache["test_id"] = mock_anime

        mock_anime.get_video = Mock(return_value=mock_stream)
        backend.player = Mock()

        result = backend.resume_anime("test_id", quality=720)

        assert result is True
        backend.player.launch.assert_called_once()

        # Verify start time includes both history timestamp and skip_intro
        start_time = backend.player.launch.call_args[1]["start_time"]
        assert start_time == 305  # 300 + 5

    def test_resume_falls_back_to_search(self, backend, mock_anime, mock_stream, monkeypatch):
        """Resume should search if anime not in cache"""
        history_entry = {
            "anime_name": "Test Anime",
            "episode": 3,
            "timestamp": 150
        }

        backend.watch_history = Mock()
        backend.watch_history.get_entry = Mock(return_value=history_entry)
        backend.cache = {}  # Empty cache

        mock_anime.get_video = Mock(return_value=mock_stream)
        backend.player = Mock()

        monkeypatch.setattr(backend, "get_anime_by_query", lambda name: [mock_anime])

        result = backend.resume_anime("missing_id")
        assert result is True

    def test_resume_fails_when_stream_unavailable(self, backend, mock_anime):
        """Resume should handle stream fetch failures"""
        history_entry = {
            "anime_name": "Test Anime",
            "episode": 5,
            "timestamp": 300
        }

        backend.watch_history = Mock()
        backend.watch_history.get_entry = Mock(return_value=history_entry)
        backend.cache["test_id"] = mock_anime

        mock_anime.get_video = Mock(return_value=None)

        result = backend.resume_anime("test_id")
        assert result is False

    def test_continue_watching_formats_correctly(self, backend):
        """Continue watching list should have correct structure"""
        raw_history = [
            ("anime1", {
                "anime_name": "Anime A",
                "episode": 5,
                "progress_percent": 75,
                "timestamp": 900,
                "last_watched": 1234567890
            }),
            ("anime2", {
                "anime_name": "Anime B",
                "episode": 1,
                "progress_percent": 20,
                "timestamp": 150,
                "last_watched": 1234567800
            })
        ]

        backend.watch_history = Mock()
        backend.watch_history.get_continue_watching = Mock(return_value=raw_history)

        result = backend.get_continue_watching_list(limit=5)

        assert len(result) == 2
        assert result[0]["anime_id"] == "anime1"
        assert result[0]["progress_percent"] == 75
        assert result[1]["anime_name"] == "Anime B"

    def test_continue_watching_respects_limit(self, backend):
        """Limit parameter should be passed to watch_history"""
        backend.watch_history = Mock()
        backend.watch_history.get_continue_watching = Mock(return_value=[])

        backend.get_continue_watching_list(limit=3)
        backend.watch_history.get_continue_watching.assert_called_once_with(3)


# ============================================================================
# PROGRESS TRACKING TESTS
# ============================================================================

class TestProgressTracking:
    def test_progress_tracker_starts_on_play(self, backend, mock_anime, mock_stream):
        """Progress tracker should start when episode plays"""
        backend.player = Mock()
        backend.watch_history = Mock()

        backend.play_episode(mock_anime, 1, mock_stream)

        backend.player.start_progress_tracker.assert_called_once()
        call_args = backend.player.start_progress_tracker.call_args

        # Verify callback is provided
        assert callable(call_args[0][0])

        # Verify interval matches settings
        assert call_args[1]["interval"] == backend.save_progress_interval

    def test_progress_callback_updates_history(self, backend, mock_anime, mock_stream):
        """Progress callback should update watch history"""
        backend.player = Mock()
        backend.watch_history = Mock()

        backend.play_episode(mock_anime, 7, mock_stream)

        # Get the progress callback
        progress_callback = backend.player.start_progress_tracker.call_args[0][0]

        # Simulate progress update
        progress_callback(600, 1440)

        backend.watch_history.update_progress.assert_called_with(
            mock_anime.identifier,
            mock_anime.name,
            7,
            600,
            1440
        )


# ============================================================================
# SETTINGS INTEGRATION TESTS
# ============================================================================

class TestSettingsIntegration:
    def test_backend_loads_all_settings(self, tmp_path):
        """Backend should load all settings from config"""
        cfg = tmp_path / "settings.yaml"
        s = settings_mod.AnimeSettings(config_path=cfg, use_yaml=True)

        s.set("quality", 1080, save=True)
        s.set("skip_intro_seconds", 10, save=True)
        s.set("skip_outro_seconds", 20, save=True)
        s.set("auto_next_episode", True, save=True)

        backend = backend_mod.AnimeBackend(settings=s)

        assert backend.global_quality == 1080
        assert backend.skip_intro_seconds == 10
        assert backend.skip_outro_seconds == 20
        assert backend.auto_next_episode is True

    def test_backend_uses_defaults_when_no_config(self):
        """Backend should work with default settings"""
        backend = backend_mod.AnimeBackend()

        assert hasattr(backend, "global_quality")
        assert hasattr(backend, "auto_next_episode")
        assert backend.settings is not None