from textual import work
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Input, ListView, ListItem, Static, Footer

from ibuki import CSS_PATH
from ..backend.utils import clean_html
from ..logs.logger import get_logger
from ..backend.backend import AnimeBackend
from .anime_detail import AnimeDetailScreen
from .episode_view import EpisodeDetailScreen

class SearchScreen(Screen):
    BINDINGS = [
        ('escape', 'go_back', 'Go Back'),
        ('s', 'synopsis', 'Synopsis')
    ]
    CSS_PATH = CSS_PATH / "search_styles.css"

    def __init__(self, backend: AnimeBackend, **kwargs):
        super().__init__(**kwargs)
        self.backend = backend
        self.logger = get_logger("SearchScreen")

    def compose(self) -> ComposeResult:
        yield Input(placeholder='Search for anime :3', id='search_input')
        yield ListView(id='search_results')
        yield Static('', id='loading_display')
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.input.value.strip()

        list_view = self.query_one('#search_results', ListView)
        list_view.clear()

        self.do_search(query)
        if not query:
            list_view.append(ListItem(Static('Anime not found! :/')))
            return

    @work(thread=True, exclusive=True, name='SearchWorker')
    def do_search(self, query: str) -> None:
        self.app.call_from_thread(self._set_loading_text, "Searching... :3")

        anime_list = self.backend.get_anime_by_query(query)
        if not anime_list:
            self.app.call_from_thread(self._set_loading_text, "Anime not found! :/")
            return

        for idx, anime in enumerate(anime_list):

            try:
                info = anime.get_info()
                title = info.name
                synopsis = clean_html(info.synopsis)
                self.app.call_from_thread(self.add_result_item, anime, title, synopsis, idx)

            except Exception as e:
                self.logger.error(f"Failed to load info for an item: {e}")

        self.app.call_from_thread(self._set_loading_text, "")

    def add_result_item(self, anime, title, synopsis, idx):
        list_view = self.query_one('#search_results', ListView)
        list_item = ListItem(Static(title))
        list_item.index = idx
        list_item.synopsis = synopsis
        list_item.anime = anime
        list_view.append(list_item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle when a user clicks or presses enter on a list item"""
        selected_item = event.item
        anime = getattr(selected_item, 'anime', None)

        if anime is None:
            self.logger.warning(f"Selected item has no anime data attached :/")
            return

        self.app.push_screen(EpisodeDetailScreen(anime, self.backend))

    def _set_loading_text(self, text: str):
        self.query_one('#loading_display', Static).update(text)

    def action_synopsis(self):
        list_view = self.query_one('#search_results', ListView)
        selected_index = list_view.index
        if selected_index is None or selected_index < 0:
            self.logger.warning("No item selected to show synopsis :/")
            return

        children = list(list_view.children)
        if selected_index >= len(children):
            self.logger.warning("Selected index out of bounds :/")
            return

        selected = children[selected_index]
        anime = getattr(selected, 'anime', None)
        synopsis = getattr(selected, 'synopsis', 'No synopsis available.')

        if anime:
            self.app.push_screen(AnimeDetailScreen(anime, synopsis))
        else:
            self.logger.warning("Selected item has no anime data attached :/")

    def action_go_back(self):
        self.app.pop_screen()