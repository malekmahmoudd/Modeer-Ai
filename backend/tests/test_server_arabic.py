"""Text the server writes, in Arabic for someone using Arabic (app.core.lang)."""

from __future__ import annotations

from datetime import date

from app.core import lang
from app.core.config import settings

AR = {"fareeq_locale": "ar"}


def _ar(client):
    client.cookies.update(AR)
    return client


def test_errors_come_back_in_arabic(client):
    _ar(client)
    missing = client.delete("/api/goals/nope")
    assert missing.status_code == 404 and missing.json()["detail"] == "لم يُعثر على الهدف"
    client.cookies.clear()
    assert client.delete("/api/goals/nope").json()["detail"] == "Goal not found"


def test_field_errors_are_translated_too(client):
    _ar(client)
    made = client.post("/api/agents/study/chat", json={"message": "hello"}).json()
    renamed = client.patch(f"/api/conversations/{made['conversation_id']}", json={"title": "  "})
    assert renamed.status_code == 422
    assert renamed.json()["detail"][0]["msg"] == "لا يمكن أن يكون العنوان فارغًا"


def test_the_language_is_the_cookie_then_the_browser_for_errors(client):
    arabic_browser = {"Accept-Language": "ar-EG,ar;q=0.9,en;q=0.5"}
    assert client.delete("/api/goals/x", headers=arabic_browser).json()["detail"] == (
        "لم يُعثر على الهدف"
    )
    client.cookies.update({"fareeq_locale": "en"})
    assert client.delete("/api/goals/x", headers=arabic_browser).json()["detail"] == (
        "Goal not found"
    )


def test_the_accounts_choice_wins_where_the_account_is_known(client):
    client.post("/api/goals", json={"title": "Run a 10k"})
    client.patch("/api/users/me", json={"locale": "en"})
    _ar(client)
    assert client.get("/api/briefings/today").json()["summary"].startswith("Your priorities")


def test_the_briefing_is_written_in_arabic_and_remade_on_a_switch(client):
    client.post("/api/goals", json={"title": "Pass the thermodynamics final"})
    _ar(client)
    arabic = client.get("/api/briefings/today").json()
    assert "أولوياتك" in arabic["summary"]
    assert any(i["text"] == "لنرتّب أولويات اليوم معًا" for i in arabic["items"])
    client.cookies.clear()
    english = client.get("/api/briefings/today").json()
    assert english["summary"].startswith("Your priorities") and english["id"] != arabic["id"]


def test_the_weekly_summary_in_arabic(client):
    _ar(client)
    week = client.get("/api/briefings/week").json()
    assert "أسبوعك" in week["summary"] or "الأيام السبعة القادمة" in week["summary"] or (
        "لم يُسجَّل" in week["summary"]
    )


def test_a_documents_read_error_is_shown_in_arabic(client):
    _ar(client)
    made = client.post(
        "/api/documents",
        files={"file": ("tiny.txt", b"hi there", "text/plain")},
        data={"agent_id": "study"},
        headers={"Origin": settings.frontend_url},
    ).json()
    doc = client.get(f"/api/documents/{made['id']}").json()
    assert doc["status"] == "failed" and doc["error"].startswith("لم يُعثر على نص مقروء")


def test_messages_with_numbers_are_translated():
    assert lang.translate("That file is over the 10 MB limit.", "ar") == (
        "حجم الملف يتجاوز ١٠ ميغابايت."
    )
    assert lang.translate(
        "The AI provider is at its usage limit. Please try again in about 3 minutes.", "ar"
    ) == "بلغ مزوّد الذكاء الاصطناعي حدّ الاستخدام. حاول مرة أخرى بعد نحو ٣ دقيقة."
    assert lang.translate("Something new we never wrote", "ar") == "Something new we never wrote"


def test_arabic_dates_and_counts_read_naturally():
    friday = date(2026, 9, 25)
    assert lang.day(date(2026, 10, 1)) == "الخميس ١ أكتوبر"
    assert lang.countdown(date(2026, 9, 26), friday) == "غدًا (السبت ٢٦ سبتمبر)"
    assert lang.countdown(date(2026, 9, 30), friday) == "الأربعاء ٣٠ سبتمبر (بعد ٥ أيام)"
    assert lang.days_phrase(2) == "يومان" and lang.days_phrase(11) == "١١ يومًا"
