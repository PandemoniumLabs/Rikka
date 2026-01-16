from textual import work
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import ListView, ListItem, Static, Footer

from ibuki import CSS_PATH
from ..backend.backend import AnimeBackend

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

    def compose(self) -> ComposeResult:
        yield Static(self.anime.name, id="title")
        yield ListView(id="episode_list")
        yield Static('', id='loading_display')
        yield Footer()

    def on_mount(self):
        self.load_episodes()

    @work(thread=True, exclusive=True, name='EpisodesWorker')
    def load_episodes(self):
        self.app.call_from_thread(self._set_loading_text, "Searching... :3")
        self.episodes = self.backend.get_episodes(self.anime)
        self.app.call_from_thread(self.populate_list)
        self.app.call_from_thread(self._set_loading_text, "")

    def populate_list(self):
        episode_list = self.query_one("#episode_list", ListView)

        if not self.episodes:
            episode_list.append(ListItem(Static("No episodes found :(")))
            return

        for idx, ep_num in enumerate(self.episodes):
            label = f"Ep {ep_num}"
            item = ListItem(Static(label))
            item.index = idx
            episode_list.append(item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle when a user clicks or presses enter on an episode"""
        selected_item = event.item
        ep_index = getattr(selected_item, "index", None)
        if ep_index is None: return

        episode_number = self.episodes[ep_index]

        stream = self.backend.get_episode_stream(
            self.anime,
            episode_number,
            self.backend.global_quality
        )

        if not stream:
            self.app.notify("No stream available for this episode :(", severity="error", timeout=3)
            return

        anime_id = getattr(self.anime, "identifier", str(id(self.anime)))
        entry = self.backend.watch_history.get_entry(anime_id)

        start_time = 0
        if entry and entry["episode"] == episode_number:
            start_time = entry["timestamp"]

        self.backend.play_episode(self.anime, episode_number, stream, start_time)

    def _set_loading_text(self, text: str):
        self.query_one('#loading_display', Static).update(text)

    def action_go_back(self):
        self.app.pop_screen()