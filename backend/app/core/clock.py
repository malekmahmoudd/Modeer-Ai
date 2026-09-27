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
    found += _resolve_arabic(message or "", today)
    return found[:6]


# --- the same, in Arabic (Egyptian, Gulf and Modern Standard) ------------------------------
# Matched on a folded copy of the text: one spelling for the alef forms, taa
# marbuta, alef maqsura and the Gulf چ, no diacritics or tatweel, and Western
# digits. Words that are ambiguous on their own stay out: "الحد" is also "the
# limit", so Egyptian Sunday counts only as "يوم الحد".

_AR_FOLD = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ة": "ه",
        "ى": "ي",
        "چ": "ك",
        "ـ": None,
        **{chr(0x0660 + d): str(d) for d in range(10)},
        **{chr(0x06F0 + d): str(d) for d in range(10)},
        **{chr(c): None for c in range(0x064B, 0x0653)},
        "\u0670": None,
    }
)
_AR_DAYS = {
    0: r"الاثنين|الاتنين",
    1: r"الثلاثاء|الثلاثا|التلات|التلاتاء",
    2: r"الاربعاء|الاربعا|الاربع",
    3: r"الخميس",
    4: r"الجمعه",
    5: r"السبت",
    6: r"الاحد|(?<=يوم )الحد",
}
_AR_NEXT = r"(?:\s+(?:الجاي|الجايه|القادم|القادمه|الياي|اليايه|اللي\s+جاي|اللي\s+جايه))?"
_AR_NUMBERS = {
    "واحد": 1, "اثنين": 2, "اتنين": 2, "ثلاث": 3, "ثلاثه": 3, "تلات": 3, "تلاته": 3,
    "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5, "ست": 6, "سته": 6, "سبع": 7,
    "سبعه": 7, "ثمان": 8, "ثماني": 8, "ثمانيه": 8, "تمن": 8, "تمانيه": 8,
    "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10,
}  # fmt: skip
_AR_NUMBER = r"\d{1,3}|" + "|".join(sorted(_AR_NUMBERS, key=len, reverse=True))
_AR_PATTERNS = [
    # the day after tomorrow, before tomorrow so it is not read as "tomorrow"
    (re.compile(r"(?<!\w)بعد\s+(?:بكره|بكرا|باكر|غدا|غد)(?!\w)"), "after"),
    (re.compile(r"(?<!\w)(?:[وف])?(?:بكره|بكرا|باكر|غدا)(?!\w)"), "tomorrow"),
    (
        re.compile(
            r"(?<!\w)(?:بعد|كمان)\s+(" + _AR_NUMBER + r")\s+"
            r"(يوم|ايام|يوما|اسبوع|اسابيع|اسبوعا)(?!\w)"
        ),
        "count",
    ),
    (re.compile(r"(?<!\w)(?:بعد|كمان)\s+(يومين|اسبوعين|يوم|اسبوع)(?!\w)"), "unit"),
    (
        re.compile(
            r"(?<!\w)(?:[وف]?يوم\s+)?[وف]?(?:"
            + "|".join(f"(?P<d{k}>{v})" for k, v in _AR_DAYS.items())
            + r")"
            + _AR_NEXT
            + r"(?!\w)"
        ),
        "weekday",
    ),
    (re.compile(r"(?<!\w)يوم\s+(\d{1,2})(?!\w)|(?<!\w)(\d{1,2})\s+(?:من\s+)?الشهر(?!\w)"), "nth"),
]


def _nth(n: int, today: date) -> date | None:
    if not 1 <= n <= 31:
        return None
    year, month = today.year, today.month
    if n <= today.day:
        month += 1
        if month > 12:
            year, month = year + 1, 1
    try:
        return date(year, month, n)
    except ValueError:
        return None


def _resolve_arabic(message: str, today: date) -> list[tuple[str, date]]:
    """Arabic date words, resolved the same way as the English ones above."""
    text = message.translate(_AR_FOLD)
    if not re.search(r"[\u0600-\u06FF]", text):
        return []
    hits: list[tuple[int, int, str, date]] = []
    for pattern, kind in _AR_PATTERNS:
        for m in pattern.finditer(text):
            day: date | None = None
            if kind == "after":
                day = today + timedelta(days=2)
            elif kind == "tomorrow":
                day = today + timedelta(days=1)
            elif kind == "count":
                raw = m.group(1)
                n = int(raw) if raw.isdigit() else _AR_NUMBERS[raw]
                weeks = m.group(2) in ("اسبوع", "اسابيع", "اسبوعا")
                day = today + timedelta(days=n * (7 if weeks else 1))
            elif kind == "unit":
                unit = m.group(1)
                days = {"يوم": 1, "يومين": 2, "اسبوع": 7, "اسبوعين": 14}[unit]
                day = today + timedelta(days=days)
            elif kind == "weekday":
                target = next(k for k in _AR_DAYS if m.group(f"d{k}"))
                day = today + timedelta(days=(target - today.weekday()) % 7 or 7)
            else:
                day = _nth(int(m.group(1) or m.group(2)), today)
            if day is None:
                continue
            # A longer phrase already covering this spot wins ("بعد بكره" over "بكره").
            if any(a <= m.start() < b or a < m.end() <= b for a, b, _, _ in hits):
                continue
            hits.append((m.start(), m.end(), m.group(0), day))
    return [(words, day) for _, _, words, day in sorted(hits)]
