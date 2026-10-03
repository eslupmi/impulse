"""Locate bundled resources in a checkout or an installed distribution."""
from pathlib import Path


def resource_directory(name: str) -> Path:
    app_directory = Path(__file__).resolve().parent
    packaged = app_directory / name
    return packaged if packaged.is_dir() else app_directory.parent / name
