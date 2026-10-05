"""Provider installation must preserve the core candidate selected by the image build."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest


def _wheel(directory, name, version, requirements=()):
    filename = directory / f"{name}-{version}-py3-none-any.whl"
    metadata_dir = f"{name}-{version}.dist-info"
    with ZipFile(filename, "w") as archive:
        archive.writestr(
            f"{metadata_dir}/METADATA",
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
            + "".join(f"Requires-Dist: {requirement}\n" for requirement in requirements),
        )
        archive.writestr(
            f"{metadata_dir}/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
        archive.writestr(f"{metadata_dir}/RECORD", "")
    return filename


@pytest.mark.parametrize("required_core", ["3.8.0", "3.8.1"])
def test_docker_provider_install_preserves_core_candidate(tmp_path, required_core):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required to exercise the image dependency resolver")
    available = tmp_path / "available"
    wheelhouse = tmp_path / "wheelhouse"
    available.mkdir()
    wheelhouse.mkdir()
    candidate = _wheel(available, "impulse_bot", "3.8.0")
    _wheel(available, "impulse_bot", "3.8.1")
    _wheel(wheelhouse, "impulse_test_provider", "1.0.0", [f"impulse-bot=={required_core}"])
    environment = {**os.environ, "UV_NO_INDEX": "1", "UV_FIND_LINKS": str(available)}
    subprocess.run(
        [uv, "venv", "--python", sys.executable, ".venv"], cwd=tmp_path,
        env=environment, check=True, capture_output=True,
    )
    subprocess.run(
        [uv, "pip", "install", "--python", ".venv/bin/python", str(candidate)],
        cwd=tmp_path, env=environment, check=True, capture_output=True,
    )
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    command = next(line.strip() for line in dockerfile.splitlines() if "uv pip install --python" in line)
    command = command.rsplit(";", 1)[0]
    result = subprocess.run(command, shell=True, cwd=tmp_path, env=environment, capture_output=True)
    assert (result.returncode == 0) == (required_core == "3.8.0"), result.stderr.decode()
    installed = subprocess.run(
        [str(tmp_path / ".venv/bin/python"), "-c",
         'from importlib.metadata import version; print(version("impulse-bot"))'],
        check=True, capture_output=True, text=True,
    )
    assert installed.stdout.strip() == "3.8.0"
