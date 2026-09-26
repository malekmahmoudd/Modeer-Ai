"""Incognito chats, search, rename, regenerate and edit, saved replies, voice
input, the interface language, and reading photos and scans with OCR."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.api.routes import voice as voice_route
from app.conversations import service as convo_service
from app.core.config import settings
from app.db.models import Conversation, Message
from app.documents import ocr
from app.documents.parse import parse
from app.users.service import get_or_create_demo_user

FACT_MSG = (
    "Just so you know, I am studying mechanical engineering at TU Delft, "
    "and I'm preparing for my thermodynamics final."
)


def _chat(client, agent, message, **extra):
    r = client.post(f"/api/agents/{agent}/chat", json={"message": message, **extra})
    assert r.status_code == 200, r.text
    return r.json()


# --- incognito --------------------------------------------------------------------------


def test_an_incognito_chat_learns_nothing_and_stays_out_of_sight(client):
    res = _chat(client, "modeer", FACT_MSG, incognito=True)
    assert not [c for c in res["memory_candidates"] if c["stored"]]
    assert client.get("/api/memory/shared").json() == []
    assert client.get("/api/conversations").json() == []
    assert client.get("/api/conversations/search", params={"q": "TU Delft"}).json() == []
    # The conversation itself is still the person's while it lasts.
    convo = client.get(f"/api/conversations/{res['conversation_id']}").json()
    assert convo["incognito"] is True and convo["expires_at"]


def test_an_incognito_chat_sends_saved_context_only_when_asked(client):
    _chat(client, "modeer", FACT_MSG)
    bare = _chat(client, "career", "What should I focus on?", incognito=True)
    assert bare["context_used"] is False
    assert bare["context"]["personal_context_count"] == 0
    opted = _chat(
        client, "career", "What should I focus on?", incognito=True, incognito_context=True
    )
    assert opted["context_used"] is True


def test_incognito_chats_are_deleted_when_their_time_is_up(client, db):
    res = _chat(client, "study", "hello", incognito=True)
    convo = db.get(Conversation, res["conversation_id"])
    convo.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    db.commit()
    client.get("/api/conversations")  # listing sweeps them
    db.expire_all()
    assert db.get(Conversation, res["conversation_id"]) is None
    assert not db.scalars(
        select(Message).where(Message.conversation_id == res["conversation_id"])
    ).all()


def test_the_hourly_sweep_removes_expired_incognito_chats_for_everyone(client, db):
    from app.main import sweep_incognito

    res = _chat(client, "study", "hello", incognito=True)
    db.get(Conversation, res["conversation_id"]).expires_at = datetime.now(UTC).replace(
        tzinfo=None
    ) - timedelta(minutes=1)
    db.commit()
    assert sweep_incognito() == 1
    db.expire_all()
    assert db.get(Conversation, res["conversation_id"]) is None


# --- search, rename, recent -----------------------------------------------------------------


def test_search_finds_messages_across_agents_and_folds_arabic(client):
    _chat(client, "study", "Help me revise thermodynamics for Friday")
    _chat(client, "career", "أريد التحضير لمقابلة في القاهرة")
    hits = client.get("/api/conversations/search", params={"q": "THERMO"}).json()
    assert {h["agent_id"] for h in hits} >= {"study"}
    assert any("thermodynamics" in h["snippet"].lower() for h in hits)
    # "مقابله" (taa marbuta written as haa) still finds "مقابلة".
    arabic = client.get("/api/conversations/search", params={"q": "مقابله"}).json()
    assert arabic and arabic[0]["agent_id"] == "career"
    assert client.get("/api/conversations/search", params={"q": "x"}).json() == []


def test_a_conversation_can_be_renamed_and_shows_in_recent(client):
    res = _chat(client, "writing", "Draft a thank-you note")
    cid = res["conversation_id"]
    renamed = client.patch(f"/api/conversations/{cid}", json={"title": "  Note to Sam "})
    assert renamed.json()["title"] == "Note to Sam"
    assert client.patch(f"/api/conversations/{cid}", json={"title": "   "}).status_code == 422
    recent = client.get("/api/conversations/recent").json()
    assert recent[0]["id"] == cid and recent[0]["title"] == "Note to Sam"


# --- regenerate and edit ------------------------------------------------------------------


def test_regenerate_drops_the_reply_and_the_retry_answers_again(client):
    res = _chat(client, "study", "Explain entropy simply")
    cid = res["conversation_id"]
    back = client.post(f"/api/conversations/{cid}/rewind", json={"mode": "regenerate"})
    assert back.json()["text"] == "Explain entropy simply"
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user"]
    again = client.post(
        "/api/agents/study/chat", json={"retry": True, "conversation_id": cid}
    ).json()
    assert again["content"]
    msgs = client.get(f"/api/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]


def test_a_saved_reply_is_never_taken_back_silently(client):
    res = _chat(client, "study", "Explain enthalpy")
    cid = res["conversation_id"]
    client.patch(f"/api/conversations/{cid}/messages/{res['message_id']}", json={"pinned": True})
    back = client.post(f"/api/conversations/{cid}/rewind", json={"mode": "regenerate"})
    assert back.status_code == 409 and "saved" in back.json()["detail"]
    assert client.get("/api/conversations/pinned").json()


def test_edit_takes_back_the_whole_turn(client):
    _chat(client, "study", "First question")
    res = _chat(client, "study", "Secnod qestion", conversation_id=None)
    cid = res["conversation_id"]
    back = client.post(f"/api/conversations/{cid}/rewind", json={"mode": "edit"})
    assert back.json()["text"] == "Secnod qestion"
    assert client.get(f"/api/conversations/{cid}").json()["messages"] == []
    nothing = client.post(f"/api/conversations/{cid}/rewind", json={"mode": "edit"})
    assert nothing.status_code == 409
    bad = client.post(f"/api/conversations/{cid}/rewind", json={"mode": "undo"})
    assert bad.status_code == 422


# --- saved replies --------------------------------------------------------------------


def test_replies_can_be_saved_listed_and_unsaved(client):
    res = _chat(client, "travel", "Plan a weekend in Alexandria")
    cid, mid = res["conversation_id"], res["message_id"]
    path = f"/api/conversations/{cid}/messages/{mid}"
    assert client.patch(path, json={"pinned": True}).status_code == 204
    saved = client.get("/api/conversations/pinned").json()
    assert saved[0]["message_id"] == mid and saved[0]["agent_id"] == "travel"
    detail = client.get(f"/api/conversations/{cid}").json()
    assert next(m for m in detail["messages"] if m["id"] == mid)["pinned_at"]
    assert client.patch(path, json={"pinned": False}).status_code == 204
    assert client.get("/api/conversations/pinned").json() == []
    # Only replies can be saved, and only through their own conversation.
    user_msg = detail["messages"][0]["id"]
    assert (
        client.patch(
            f"/api/conversations/{cid}/messages/{user_msg}", json={"pinned": True}
        ).status_code
        == 404
    )
    assert (
        client.patch(f"/api/conversations/other/messages/{mid}", json={"pinned": True}).status_code
        == 404
    )


def test_saved_replies_go_with_their_conversation(client, db):
    res = _chat(client, "travel", "Plan a weekend in Luxor")
    user = get_or_create_demo_user(db)
    convo_service.set_pinned(db, user.id, res["message_id"], True)
    db.commit()
    client.delete(f"/api/conversations/{res['conversation_id']}")
    assert client.get("/api/conversations/pinned").json() == []


# --- interface language --------------------------------------------------------------


def test_the_interface_language_is_saved_on_the_account(client):
    assert client.patch("/api/users/me", json={"locale": "ar"}).json()["locale"] == "ar"
    assert client.get("/api/users/me").json()["locale"] == "ar"
    assert client.patch("/api/users/me", json={"locale": "fr"}).status_code == 422
    assert client.patch("/api/users/me", json={"locale": None}).json()["locale"] is None


# --- voice ----------------------------------------------------------------------------


def _clip(client, data=b"\x1aE\xdf\xa3" + b"0" * 2000, kind="audio/webm;codecs=opus"):
    return client.post(
        "/api/voice/transcribe",
        files={"audio": ("clip.webm", data, kind)},
        headers={"Origin": settings.frontend_url},
    )


def test_voice_says_when_it_is_not_available(client):
    assert client.get("/api/voice").json()["transcribe"] is False  # the mock provider
    assert _clip(client).status_code == 503


def test_voice_turns_a_clip_into_text_and_keeps_nothing(client, monkeypatch):
    monkeypatch.setattr(voice_route.voice, "available", lambda: True)
    heard = {}

    async def fake(audio, content_type, *, language=None):
        heard.update(size=len(audio), type=content_type, language=language)
        return "بكرة عندي مقابلة"

    monkeypatch.setattr(voice_route.voice, "transcribe", fake)
    r = _clip(client)
    assert r.status_code == 200 and r.json() == {"text": "بكرة عندي مقابلة"}
    assert heard["type"].startswith("audio/webm")
    assert _clip(client, kind="video/avi").status_code == 415
    assert _clip(client, data=b"tiny").status_code == 400
    monkeypatch.setattr(settings, "voice_max_bytes", 1500)
    assert _clip(client).status_code == 413


def test_voice_has_a_daily_limit(client, monkeypatch):
    monkeypatch.setattr(voice_route.voice, "available", lambda: True)

    async def fake(audio, content_type, *, language=None):
        return "hello"

    monkeypatch.setattr(voice_route.voice, "transcribe", fake)
    monkeypatch.setattr(settings, "voice_per_day", 1)
    assert _clip(client).status_code == 200
    assert _clip(client).status_code == 429


# --- OCR ------------------------------------------------------------------------------

needs_ocr = pytest.mark.skipif(not ocr.available(), reason="Tesseract or its data is missing")


def _picture(lines, size=(1400, 420)):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=48)
    for i, line in enumerate(lines):
        draw.text((60, 60 + i * 120), line, fill="black", font=font)
    return image


def test_images_are_turned_upright_and_scaled_before_reading():
    from PIL import Image

    tall = Image.new("RGB", (400, 300), "white")
    exif = tall.getexif()
    exif[0x0112] = 6  # "rotate 90° clockwise to display"
    buffer = io.BytesIO()
    tall.save(buffer, "JPEG", exif=exif)
    prepared = ocr.prepare(Image.open(io.BytesIO(buffer.getvalue())))
    assert prepared.mode == "L"
    assert prepared.height > prepared.width  # turned the right way up
    assert max(prepared.size) == 2400  # small photos are enlarged


@needs_ocr
def test_a_photo_is_read_with_ocr():
    buffer = io.BytesIO()
    _picture(["Senior Data Analyst, Berlin", "Python and SQL since 2019"]).save(buffer, "PNG")
    pages = parse(buffer.getvalue(), "image")
    assert pages[0].ocr is True
    assert "Senior Data Analyst" in pages[0].text and "2019" in pages[0].text


@needs_ocr
def test_a_scanned_pdf_page_is_read_with_ocr():
    buffer = io.BytesIO()
    _picture(["Thermodynamics final exam", "Friday 9:00, Hall B"]).save(buffer, "PDF")
    pages = parse(buffer.getvalue(), "pdf")
    assert pages[0].ocr is True and "Thermodynamics" in pages[0].text


@needs_ocr
def test_an_uploaded_photo_becomes_a_document_with_a_note(client):
    buffer = io.BytesIO()
    _picture(["Monthly budget: rent 9000 EGP", "Groceries 2500 EGP"]).save(buffer, "JPEG")
    made = client.post(
        "/api/documents",
        files={"file": ("budget.jpg", buffer.getvalue(), "image/jpeg")},
        data={"agent_id": "finance"},
        headers={"Origin": settings.frontend_url},
    )
    assert made.status_code == 202, made.text
    doc = client.get(f"/api/documents/{made.json()['id']}").json()
    assert doc["kind"] == "image" and doc["status"] == "ready"
    assert "rent" in doc["preview"].lower()
    assert "may be wrong" in doc["error"]
