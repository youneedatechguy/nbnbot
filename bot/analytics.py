"""Agent Analytics tracking module."""

import logging
import os
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

ANALYTICS_ENDPOINT = os.environ.get("ANALYTICS_ENDPOINT", "")
ANALYTICS_API_KEY = os.environ.get("ANALYTICS_API_KEY", "")
ANALYTICS_ENABLED = os.environ.get("ANALYTICS_ENABLED", "true").lower() == "true"
ENABLED = ANALYTICS_ENABLED or bool(ANALYTICS_ENDPOINT)


def _get_events_file() -> Path:
    """Get the path to the events log file."""
    return Path(os.environ.get("ANALYTICS_EVENTS_FILE", "/mnt/apps/yambabroadband/api/analytics_events.jsonl"))


def track_event(
    event_name: str,
    properties: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> bool:
    """Track an analytics event.

    Args:
        event_name: Name of the event
        properties: Additional properties to track
        user_id: User identifier

    Returns:
        True if event was tracked successfully
    """
    if not ENABLED:
        logger.debug(f"Analytics disabled, skipping event: {event_name}")
        return False

    event = {
        "event": event_name,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "properties": properties or {},
    }

    if user_id:
        event["user_id"] = user_id

    events_file = _get_events_file()
    events_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(events_file, "a") as f:
            f.write(json.dumps(event) + "\n")
        logger.info(f"Tracked event: {event_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to track event {event_name}: {e}")
        return False


def track_bot_started() -> bool:
    """Track bot startup event."""
    return track_event("bot_started", {"source": "telegram_bot"})


def track_address_lookup(user_id: str, address: str, success: bool) -> bool:
    """Track address lookup event."""
    return track_event(
        "address_lookup",
        {"address": address, "success": success},
        user_id=user_id,
    )


def track_command_used(command: str, user_id: Optional[str] = None) -> bool:
    """Track command usage."""
    return track_event(
        "command_used",
        {"command": command},
        user_id=user_id,
    )


def track_error(error_type: str, message: str, user_id: Optional[str] = None) -> bool:
    """Track error event."""
    return track_event(
        "error",
        {"error_type": error_type, "message": message},
        user_id=user_id,
    )
