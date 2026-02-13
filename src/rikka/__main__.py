from textual.app import App

from src.rikka.screens.home import Home
from src.rikka.backend.backend import AnimeBackend

class Rikka(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.backend = AnimeBackend()

    def on_mount(self):
        self.push_screen(Home(self.backend))

app = Rikka()

def run():
    app.run()

if __name__ == "__main__":
    run()