import argparse
import asyncio
from pathlib import Path

from app.config.environment import get_environment_config
from app.logging import logger
from app.ui.authentication.session_store import FileSessionStore

SESSION_CLEANUP_INTERVAL_SECONDS = 60 * 60


async def run_session_cleanup(store: FileSessionStore) -> None:
    while True:
        sweep = asyncio.create_task(asyncio.to_thread(store.cleanup_expired))
        try:
            removed = await asyncio.shield(sweep)
            if removed:
                logger.info("Removed expired auth sessions", extra={"removed": removed})
        except asyncio.CancelledError:
            # Canceling the awaiter does not stop the storage worker.
            await asyncio.gather(sweep, return_exceptions=True)
            raise
        except OSError as exc:
            logger.warning("Failed to clean up expired auth sessions", extra={"error": str(exc)})
        await asyncio.sleep(SESSION_CLEANUP_INTERVAL_SECONDS)


def cleanup_expired_sessions(root_dir: str) -> int:
    store = FileSessionStore(root_dir=root_dir)
    return store.cleanup_expired()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup expired auth sessions")
    parser.add_argument(
        "--root-dir",
        default=str(Path(get_environment_config().storage_root) / "sessions"),
        help="Root sessions directory",
    )
    args = parser.parse_args()
    removed = cleanup_expired_sessions(args.root_dir)
    print(f"Removed {removed} expired sessions")


if __name__ == "__main__":
    main()
