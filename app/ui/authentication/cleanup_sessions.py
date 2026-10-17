import argparse
from pathlib import Path

from app.config.environment import get_environment_config
from app.ui.authentication.session_store import FileSessionStore


def cleanup_expired_sessions(root_dir: str) -> int:
    store = FileSessionStore(root_dir=root_dir)
    return store.cleanup_expired()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup expired auth sessions")
    parser.add_argument(
        "--root-dir",
        default=str(Path(get_environment_config().data_path) / "sessions"),
        help="Root sessions directory",
    )
    args = parser.parse_args()
    removed = cleanup_expired_sessions(args.root_dir)
    print(f"Removed {removed} expired sessions")


if __name__ == "__main__":
    main()
