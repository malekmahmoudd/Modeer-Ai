"""The user's local time.

Agents are told today's date and the time in the user's own timezone, so that
"interview next Thursday" means a real day. The zone is an IANA name the
browser reports ("Europe/London"), stored on the account; until one is known,
agents get UTC and are told the local date may differ by one day.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: Longest IANA name in use is ~32 characters; anything longer is not one.
MAX_ZONE_NAME = 64


@lru_cache(maxsize=512)
def zone(name: str | None) -> ZoneInfo | None:
    """The zone for an IANA name, or None when it is not a real zone here.

    Also None when the server has no timezone database: the user is then
    treated as having no known zone rather than the request failing.
    """
    if not name or len(name) > MAX_ZONE_NAME or name.startswith(("/", ".")) or ".." in name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def valid_zone(name: str | None) -> str | None:
    """``name`` when it names a usable zone, else None."""
    name = (name or "").strip()
    return name if zone(name) is not None else None


def now_for(user) -> tuple[datetime, str | None]:
    """The current time for this user, and the zone name it is in (None = UTC)."""
    name = valid_zone(getattr(user, "timezone", None))
    if name is None:
        return datetime.now(UTC), None
    return datetime.now(zone(name)), name


def today_for(user) -> date:
    return now_for(user)[0].date()
