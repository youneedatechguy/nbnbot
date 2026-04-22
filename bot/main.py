"""Entry point for the NBN Address Lookup Telegram bot."""

import logging
import os
import sys
from pathlib import Path

from .handlers import build_application

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Try to import tracking module
try:
    sys.path.insert(0, "/mnt/apps/yambabroadband/analytics")
    from tracking import track_bot_started
except ImportError:
    def track_bot_started(*args, **kwargs): pass
    logger.warning("tracking module not available - analytics disabled")


def _load_env_file() -> None:
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    _load_env_file()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set.")
        sys.exit(1)

    logger.info("Starting NBN Address Lookup bot…")
    track_bot_started()
    app = build_application(token)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
