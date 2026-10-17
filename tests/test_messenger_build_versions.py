"""The image installs Python dependencies from requirements.txt."""
from pathlib import Path


def test_dockerfile_installs_requirements_only():
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    run_commands = [line.strip() for line in dockerfile.splitlines() if line.startswith("RUN ")]
    assert run_commands == ["RUN pip install -r requirements.txt"]
