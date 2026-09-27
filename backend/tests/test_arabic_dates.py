"""Arabic date words resolve to real dates, like the English ones (clock.py)."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.clock import resolve_dates

FRIDAY = date(2026, 9, 25)


def _day(message: str) -> str | None:
    found = resolve_dates(message, FRIDAY)
    return found[0][1].isoformat() if found else None


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # tomorrow, in Egyptian, Gulf and Standard Arabic
        ("عندي مقابلة بكرة", "2026-09-26"),
        ("بكرا الصبح", "2026-09-26"),
        ("باچر عندي اجتماع", "2026-09-26"),
        ("غدًا", "2026-09-26"),
        # the day after tomorrow wins over "tomorrow" inside it
        ("بعد بكرة", "2026-09-27"),
        ("بعد غد", "2026-09-27"),
        # a weekday is the next one after today, with or without "next"
        ("الخميس الجاي", "2026-10-01"),
        ("يوم الخميس القادم", "2026-10-01"),
        ("الجمعة الجاية", "2026-10-02"),  # today is Friday: a week on
        ("الأربع اللي جاي", "2026-09-30"),
        ("والسبت", "2026-09-26"),
        ("يوم الحد", "2026-09-27"),
        # counts, in digits of either kind or in words
        ("بعد ٣ أيام", "2026-09-28"),
        ("بعد 3 ايام", "2026-09-28"),
        ("بعد يومين", "2026-09-27"),
        ("كمان أسبوعين", "2026-10-09"),
        ("بعد أسبوع", "2026-10-02"),
        ("بعد ثلاث أسابيع", "2026-10-16"),
        # a day of the month is the next one
        ("امتحاني يوم ٢٠", "2026-10-20"),
        ("٣٠ الشهر", "2026-09-30"),
    ],
)
def test_arabic_date_words(message, expected):
    assert _day(message) == expected


def test_words_that_only_look_like_dates_are_left_alone():
    assert resolve_dates("الحد الأقصى للميزانية", FRIDAY) == []  # "the limit", not Sunday
    assert resolve_dates("عندي ثلاث أفكار", FRIDAY) == []
    assert resolve_dates("يوم ٤٥", FRIDAY) == []


def test_english_and_arabic_in_one_message():
    found = resolve_dates("interview next Thursday and بكرة a call", FRIDAY)
    assert [d.isoformat() for _, d in found] == ["2026-10-01", "2026-09-26"]


def test_the_analysis_is_told_the_worked_out_dates():
    from app.memory.llm_extraction import _system_prompt

    prompt = _system_prompt(
        agent_id="career",
        today=FRIDAY,
        known_keys=[],
        goals=None,
        handoffs=False,
        tracking=True,
        message="عندي مقابلة الخميس الجاي",
    )
    assert '"الخميس الجاي" = Thu 01 Oct 2026' in prompt
