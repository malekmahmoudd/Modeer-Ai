"""The user's local time.

Agents are told today's date and the time in the user's own timezone, so that
"interview next Thursday" means a real day. The zone is an IANA name the
browser reports ("Europe/London"), stored on the account; until one is known,
agents get UTC and are told the local date may differ by one day.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
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


# --- relative dates in a message -----------------------------------------------------

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_RELATIVE = re.compile(
    r"\b(?:(next|this|on|coming)\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b"
    r"|\b(tomorrow|day after tomorrow)\b"
    r"|\bin\s+(\d{1,3})\s+(day|week)s?\b"
    r"|\bthe\s+(\d{1,2})(?:st|nd|rd|th)\b",
    re.I,
)


def resolve_dates(message: str, today: date) -> list[tuple[str, date]]:
    """The date words in a message, resolved against today: ("next Thursday",
    Thu 1 Oct). Models carry the calendar of their training year and get weekday
    arithmetic wrong, so this is done in code and handed to them as fact.

    A weekday means the next one after today ("next Thursday" on a Friday is
    six days away, the usual reading); "the 20th" means the next 20th.
    """
    found: list[tuple[str, date]] = []
    for match in _RELATIVE.finditer(message or ""):
        words = match.group(0)
        if match.group(2):
            target = _WEEKDAYS.index(match.group(2).lower())
            ahead = (target - today.weekday()) % 7 or 7
            day = today + timedelta(days=ahead)
        elif match.group(3):
            day = today + timedelta(days=2 if "after" in match.group(3).lower() else 1)
        elif match.group(4):
            n = int(match.group(4))
            day = today + timedelta(days=n * (7 if match.group(5).lower() == "week" else 1))
        else:
            n = int(match.group(6))
            if not 1 <= n <= 31:
                continue
            year, month = today.year, today.month
            if n <= today.day:
                month += 1
                if month > 12:
                    year, month = year + 1, 1
            try:
                day = date(year, month, n)
            except ValueError:
                continue  # "the 31st" in a 30-day month: leave it to them
        found.append((words, day))
    return found[:6]
