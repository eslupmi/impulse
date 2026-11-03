from hashlib import sha256
from pathlib import Path

from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope


class VersionedStaticFiles(StaticFiles):
    def __init__(self, directory: Path):
        super().__init__(directory=directory)
        # shortcut: files must stay unchanged until restart; snapshot them if live updates are needed.
        version = sha256()
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                version.update(path.relative_to(directory).as_posix().encode())
                version.update(b"\0")
                version.update(sha256(path.read_bytes()).digest())
        self.version = version.hexdigest()

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
