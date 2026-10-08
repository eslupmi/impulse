import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.logging import logger
from app.storage import FileStorage, S3Storage, get_storage
from app.ui.authentication.models.auth_session import AuthSession

_SESSION_ID_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class FileSessionStore:
    """YAML sessions using the selected storage backend; local writes remain atomic."""

    def __init__(self, root_dir: str, storage: FileStorage | S3Storage | None = None):
        self.root_dir = Path(root_dir)
        self._storage = storage or get_storage()

    def save_session(self, session: AuthSession) -> None:
        path = self._session_path(session.session_id)
        if not path:
            raise ValueError("invalid session id")

        payload = {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
        }

        if not isinstance(self._storage, FileStorage):
            with self._storage.open(path, "w", encoding="utf-8") as handle:
                yaml.safe_dump(payload, handle, sort_keys=False)
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(temp_name)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        self._fsync_dir(path.parent)

    def load_session(self, session_id: str) -> AuthSession | None:
        path = self._session_path(session_id)
        if not path:
            return None

        try:
            with self._storage.open(path, encoding="utf-8") as handle:
                raw = handle.read()
            data = yaml.safe_load(raw) if raw.strip() else {}
            if not isinstance(data, dict):
                return None
            session = AuthSession.model_validate(data)
        except FileNotFoundError:
            return None
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            logger.warning("Failed to parse auth session file", extra={"path": str(path), "error": str(exc)})
            return None

        if session.session_id != session_id:
            return None

        if self._is_expired(session.expires_at):
            self.delete_session(session_id)
            return None
        return session

    def delete_session(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if path:
            try:
                self._storage.remove(path)
            except FileNotFoundError:
                pass

    def cleanup_expired(self) -> int:
        if not self._storage.exists(self.root_dir):
            return 0

        removed = 0
        now = datetime.now(timezone.utc)
        for filename in self._storage.listdir(self.root_dir):
            if not filename.endswith(".yaml"):
                continue
            path = self.root_dir / filename
            try:
                with self._storage.open(path, encoding="utf-8") as handle:
                    raw = handle.read()
                data = yaml.safe_load(raw) if raw.strip() else {}
                if not isinstance(data, dict):
                    continue
                session = AuthSession.model_validate(data)
            except (OSError, yaml.YAMLError, ValidationError):
                logger.warning("Failed to load session file", extra={"path": str(path)})
                continue

            if self._is_expired(session.expires_at, now):
                try:
                    self._storage.remove(path)
                except FileNotFoundError:
                    pass
                removed += 1
        return removed

    def _session_path(self, session_id: str) -> Path | None:
        if not _SESSION_ID_PATTERN.fullmatch(session_id):
            return None
        return self.root_dir / f"{session_id}.yaml"

    @staticmethod
    def _is_expired(expires_at: datetime, now: datetime | None = None) -> bool:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = now or datetime.now(timezone.utc)
        return expires_at <= now

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        if os.name == "nt":
            return
        try:
            fd = os.open(path, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            return
