"""Assessment clock: always REFERENCE_NOW, never the host system clock."""

from datetime import datetime

from app.config import get_settings


def reference_now() -> datetime:
    """Return the configured timezone-aware reference instant."""
    return get_settings().reference_now
