import json
import os
import threading
from typing import Dict, List, Optional

from app.config.environment import get_environment_config
from app.logging import logger
from app.maintenance.models import MaintenanceWindow


class MaintenanceStore:
    def __init__(self):
        env_config = get_environment_config()
        self._dir = os.path.join(env_config.data_path, "maintenance")
        self._file = os.path.join(self._dir, "windows.json")
        self._lock = threading.Lock()
        self._windows: Dict[str, MaintenanceWindow] = {}
        self._ensure_dir()
        self._load()

    def list(self) -> List[MaintenanceWindow]:
        with self._lock:
            return list(self._windows.values())

    def get(self, window_id: str) -> Optional[MaintenanceWindow]:
        with self._lock:
            return self._windows.get(window_id)

    def upsert(self, window: MaintenanceWindow) -> MaintenanceWindow:
        with self._lock:
            self._windows[window.id] = window
            self._save_unlocked()
        return window

    def delete(self, window_id: str) -> bool:
        with self._lock:
            if window_id not in self._windows:
                return False
            del self._windows[window_id]
            self._save_unlocked()
        return True

    def _ensure_dir(self) -> None:
        if not os.path.exists(self._dir):
            os.makedirs(self._dir)
            logger.info("Created maintenance directory", extra={"path": self._dir})

    def _load(self) -> None:
        if not os.path.exists(self._file):
            return
        try:
            with open(self._file, "r") as f:
                data = json.load(f)
            for item in data.get("windows", []):
                try:
                    window = MaintenanceWindow.from_dict(item)
                    self._windows[window.id] = window
                except Exception as e:
                    logger.error("Failed to load maintenance window", extra={"error": str(e), "item": item})
        except Exception as e:
            logger.error("Failed to load maintenance store", extra={"error": str(e), "path": self._file})

    def _save_unlocked(self) -> None:
        data = {"windows": [w.to_dict() for w in self._windows.values()]}
        try:
            with open(self._file, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error("Failed to save maintenance store", extra={"error": str(e), "path": self._file})


_store: Optional[MaintenanceStore] = None


def get_maintenance_store() -> MaintenanceStore:
    global _store
    if _store is None:
        _store = MaintenanceStore()
    return _store
