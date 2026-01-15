from textual.app import App
from .screens.home import IbukiHome
from .backend.backend_v3 import AnimeBackend

class Ibuki(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.backend = AnimeBackend()

    def on_mount(self):
        self.push_screen(IbukiHome(self.backend))

app = Ibuki()

def run():
    app.run()

if __name__ == "__main__":
    run()