"""Provider installation must preserve the core and prevent third-party source builds."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
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


def _docker_install_command():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    return re.search(r"uv pip install --python .*?(?=;\s*fi)", re.sub(r"\\\n\s*", " ", dockerfile)).group()


@pytest.fixture
def wheel_environment(tmp_path):
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required to exercise the image dependency resolver")
    available = tmp_path / "available"
    (tmp_path / "wheelhouse").mkdir()
    available.mkdir()
    candidate = _wheel(available, "impulse_bot", "3.8.0")
    environment = {**os.environ, "UV_NO_INDEX": "1", "UV_FIND_LINKS": str(available)}
    subprocess.run(
        [uv, "venv", "--python", sys.executable, ".venv"], cwd=tmp_path,
        env=environment, check=True, capture_output=True,
    )
    subprocess.run(
        [uv, "pip", "install", "--python", ".venv/bin/python", str(candidate)],
        cwd=tmp_path, env=environment, check=True, capture_output=True,
    )
    return environment


@pytest.mark.parametrize("required_core", ["3.8.0", "3.8.1"])
def test_docker_provider_install_preserves_core_candidate(tmp_path, wheel_environment, required_core):
    _wheel(tmp_path / "available", "impulse_bot", "3.8.1")
    _wheel(tmp_path / "wheelhouse", "impulse_test_provider", "1.0.0", [f"impulse-bot=={required_core}"])
    result = subprocess.run(
        _docker_install_command(), shell=True, cwd=tmp_path, env=wheel_environment, capture_output=True,
    )
    assert (result.returncode == 0) == (required_core == "3.8.0"), result.stderr.decode()
    installed = subprocess.run(
        [str(tmp_path / ".venv/bin/python"), "-c",
         'from importlib.metadata import version; print(version("impulse-bot"))'],
        check=True, capture_output=True, text=True,
    )
    assert installed.stdout.strip() == "3.8.0"


def test_docker_provider_dependencies_do_not_execute_source_builds(tmp_path, wheel_environment):
    marker = tmp_path / "backend-executed"
    source = tmp_path / "source"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[build-system]\nrequires = []\nbuild-backend = "backend"\nbackend-path = ["."]\n'
        '[project]\nname = "impulse-source-probe"\nversion = "1.0.0"\n',
    )
    (source / "backend.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError('backend executed')\n",
    )
    with tarfile.open(tmp_path / "available/impulse_source_probe-1.0.0.tar.gz", "w:gz") as archive:
        archive.add(source, arcname="impulse_source_probe-1.0.0")
    _wheel(
        tmp_path / "wheelhouse", "impulse_test_provider", "1.0.0",
        ["impulse-bot==3.8.0", "impulse-source-probe==1.0.0"],
    )
    result = subprocess.run(
        _docker_install_command(), shell=True, cwd=tmp_path, env=wheel_environment, capture_output=True,
    )
    assert result.returncode != 0
    assert not marker.exists()
    assert b"building from source is disabled" in result.stderr
