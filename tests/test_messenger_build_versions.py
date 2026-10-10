"""Provider installation must preserve the core and prevent third-party source builds."""
import os
from pathlib import Path
import re
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
    return re.search(r'python -m pip install --only-binary=:all:\s+"impulse-bot==.*?(?=;\s*fi)',
                     re.sub(r"\\\n\s*", " ", dockerfile)).group()


@pytest.fixture
def wheel_environment(tmp_path):
    available = tmp_path / "available"
    (tmp_path / "wheelhouse").mkdir()
    available.mkdir()
    candidate = _wheel(available, "impulse_bot", "3.8.0")
    python = tmp_path / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    environment = {
        **os.environ, "PIP_NO_INDEX": "1", "PIP_FIND_LINKS": str(available),
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PATH": f"{python.parent}{os.pathsep}{os.environ['PATH']}",
    }
    subprocess.run(
        [sys.executable, "-m", "venv", ".venv"], cwd=tmp_path,
        env=environment, check=True, capture_output=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", str(candidate)],
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
    if required_core != "3.8.0":
        assert b"ResolutionImpossible" in result.stderr
        assert b"impulse-bot==3.8.1" in result.stdout
    installed = subprocess.run(
        ["python", "-c",
         'from importlib.metadata import version; print(version("impulse-bot"))'],
        env=wheel_environment, check=True, capture_output=True, text=True,
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
    assert b"Could not find a version that satisfies the requirement impulse-source-probe==1.0.0" in result.stderr
    assert b"No matching distribution found" in result.stderr
