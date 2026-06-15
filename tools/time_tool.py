"""Time utility for Terramon agents — provides current time and day phase."""

from datetime import datetime
from typing import Literal


def get_current_time() -> str:
    """Return current local time as ISO 8601 string."""
    return datetime.now().isoformat()


def get_day_phase(
    now: datetime | None = None,
) -> Literal["morning", "afternoon", "evening", "night"]:
    """Determine phase of day from a datetime (defaults to now)."""
    now = now or datetime.now()
    h = now.hour
    if 5 <= h < 12:
        return "morning"
    elif 12 <= h < 18:
        return "afternoon"
    elif 18 <= h < 22:
        return "evening"
    else:
        return "night"