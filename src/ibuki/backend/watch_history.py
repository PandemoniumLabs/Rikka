import json
from pathlib import Path
from datetime import datetime
from platformdirs import user_data_dir

from ..logs.logger import get_logger

class WatchHistory:
    def __init__(self):
        self.data_dir = Path(user_data_dir("ibuki", "XeonXE534"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.data_dir / "progress.json"

        self.logger = get_logger("WatchHistory")
        self.history = self.load()

    def load(self):
        if self.file_path.exists():
            try:
                return json.loads(self.file_path.read_text())

            except Exception as e:
                self.logger.error("Failed to load watch history: " + str(e) + ":/")
                return {}

        return {}

    def save(self):
        try:
            self.file_path.write_text(json.dumps(self.history, indent=2))

        except Exception as e:
            self.logger.error("Failed to save watch history: " + str(e) + ":/")

    def update_progress(self, anime_id, anime_name, episode, timestamp, total_duration):
        if isinstance(anime_id, int):
            self.logger.warning(f"Received memory ID for {anime_name}. History might not persist!")

        percent = 0
        if total_duration > 0:
            percent = round((timestamp / total_duration) * 100, 1)

        self.history[anime_id] = {
            "anime_name": anime_name,
            "episode": episode,
            "timestamp": timestamp,
            "total_duration": total_duration,
            "last_watched": datetime.now().isoformat(),
            "progress_percent": percent,
        }
        self.save()
        self.logger.debug(f"Updated {anime_name} EP{episode}: {timestamp}s :3")

    def get_continue_watching(self, limit=10):
        active = {}

        for k, v in self.history.items():
            if 5 < v["timestamp"] < v["total_duration"] * 0.95:
                active[k] = v

        sorted_items = sorted(
            active.items(), key=lambda x: x[1]["last_watched"], reverse=True
        )
        return sorted_items[:limit]

    def get_entry(self, anime_id):
        return self.history.get(anime_id)

    def remove_entry(self, anime_id):
        if anime_id in self.history:
            del self.history[anime_id]
            self.save()
            self.logger.info(f"Removed {anime_id} from watch history >:3")