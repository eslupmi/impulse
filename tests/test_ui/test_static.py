import os
import re
import shutil
from types import SimpleNamespace
from urllib.parse import urljoin

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.resources import resource_directory
from app.routes import create_router


@pytest.fixture
def static_directory(tmp_path):
    return shutil.copytree(resource_directory("static"), tmp_path / "static")


@pytest.fixture
def make_client(monkeypatch, static_directory):
    monkeypatch.setattr("app.routes.resource_directory", lambda name: static_directory)
    monkeypatch.setattr("app.routes.get_config", lambda: SimpleNamespace(ui_config=True))

    def create(http_prefix=""):
        app = FastAPI()
        app.include_router(create_router(http_prefix, fastapi_app=app))
        return TestClient(app)

    return create


def main_url(client, http_prefix=""):
    response = client.get(f"{http_prefix}/")
    assert response.status_code == 200
    match = re.search(r'src="([^"]+/js/main\.js)"', response.text)
    assert match
    return match[1]


@pytest.mark.parametrize("http_prefix", ["", "/impulse"])
def test_html_revalidates_and_all_local_assets_are_versioned(make_client, static_directory, http_prefix):
    client = make_client(http_prefix)
    response = client.get(f"{http_prefix}/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    entrypoint = main_url(client, http_prefix)
    assert re.fullmatch(rf"{http_prefix}/static/[0-9a-f]+/js/main\.js", entrypoint)
    static_base = entrypoint.removesuffix("/js/main.js")
    assert f'data-static-version="{static_base.rsplit("/", 1)[1]}"' in response.text

    assets = re.findall(r'(?:src|href)="([^"]+)"', response.text)
    pending = [url for url in assets if url.startswith("/")]
    visited = set()
    while pending:
        url = pending.pop()
        if url in visited:
            continue
        visited.add(url)
        assert url.startswith(f"{static_base}/")
        asset = client.get(url)
        assert asset.status_code == 200, url
        assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
        if url.endswith(".js"):
            imports = re.findall(r'\bfrom\s*["\']([^"\']+)["\']', asset.text)
            pending.extend(urljoin(url, dependency) for dependency in imports)

    assert f"{static_base}/js/table.js" in visited
    asset = client.get(entrypoint)
    cached = client.get(entrypoint, headers={"If-None-Match": asset.headers["etag"]})
    assert cached.status_code == 304
    assert cached.headers["cache-control"] == asset.headers["cache-control"]
    assert client.head(entrypoint).headers["cache-control"] == asset.headers["cache-control"]
    assert client.get(f"{static_base}/missing.js").status_code == 404
    legacy = client.get(f"{http_prefix}/static/js/main.js")
    assert legacy.status_code == 200
    assert legacy.content == (static_directory / "js/main.js").read_bytes()


@pytest.mark.parametrize("http_prefix", ["", "/impulse"])
def test_websocket_sends_loaded_asset_version_on_connect_and_reconnect(make_client, http_prefix):
    client = make_client(http_prefix)
    client.app.state.maintenance_manager = SimpleNamespace(active_windows_payload=lambda: [])
    version = main_url(client, http_prefix).split("/")[-3]

    for _ in range(2):
        with client.websocket_connect(f"{http_prefix}/ws") as websocket:
            assert websocket.receive_json() == {"event": "static_version", "data": version}
            assert websocket.receive_json() == {"event": "active_maintenance", "data": []}
            websocket.send_json({"event": "ping"})
            assert websocket.receive_json() == {"event": "pong"}


@pytest.mark.parametrize("asset_path", ["js/table.js", "js/vendor/luxon.min.js", "css/colors.css", "index.html"])
def test_content_changes_version_even_with_same_size_and_mtime(make_client, static_directory, asset_path):
    original_url = main_url(make_client())
    original_main = (static_directory / "js/main.js").read_bytes()
    asset = static_directory / asset_path
    metadata = asset.stat()
    original_content = asset.read_bytes()
    content = original_content[:-1] + (b" " if original_content[-1:] != b" " else b"\n")
    asset.write_bytes(content)
    os.utime(asset, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))

    client = make_client()
    updated_url = main_url(client)

    assert updated_url != original_url
    assert (static_directory / "js/main.js").read_bytes() == original_main
    assert client.get(original_url).status_code == 404
    assert client.get(f"{updated_url.removesuffix('/js/main.js')}/{asset_path}").content == content


def test_asset_additions_renames_and_removals_change_version(make_client, static_directory):
    original_url = main_url(make_client())
    asset = static_directory / "icons/extra.svg"
    asset.write_text("<svg/>", encoding="utf-8")
    added_url = main_url(make_client())
    assert added_url != original_url

    renamed = asset.rename(asset.with_name("extra-renamed.svg"))
    assert main_url(make_client()) != added_url

    renamed.unlink()
    assert main_url(make_client()) == original_url


def test_version_stays_stable_across_restarts_and_mtime_changes(make_client, static_directory):
    original_url = main_url(make_client())
    asset = static_directory / "js/table.js"
    metadata = asset.stat()
    os.utime(asset, ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000_000))

    assert main_url(make_client()) == original_url


def test_disabled_ui_does_not_mount_static_files(monkeypatch):
    monkeypatch.setattr("app.routes.get_config", lambda: SimpleNamespace(ui_config=None))
    app = FastAPI()
    app.include_router(create_router("", fastapi_app=app))
    client = TestClient(app)

    assert client.get("/").status_code == 405
    assert client.get("/static/js/main.js").status_code == 404
