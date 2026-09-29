"""Voice capture, templates, organising chats, dialect and spoken replies, the CV
builder and importing from another assistant."""

from __future__ import annotations

import io
import zipfile
from datetime import date, timedelta

from app.agents import context as context_module
from app.api.routes import memory as memory_routes
from app.api.routes import tracking as tracking_routes
from app.memory.extraction import Candidate
from app.memory.llm_extraction import CheckInItem, Event, TurnAnalysis


def _fact(key, value, *, scope="shared", confidence=0.9, category="work", sensitive=False):
    return Candidate(
        scope=scope,
        agent_id=None,
        category=category,
        key=key,
        value=value,
        confidence=confidence,
        sensitive=sensitive,
        stored=True,
        reason="",
    )


# --- voice capture and check-ins ---------------------------------------------------------


def test_capture_proposes_without_saving(client, monkeypatch):
    due = date.today() + timedelta(days=3)

    async def fake(text, **_):
        return TurnAnalysis(
            checkins=[CheckInItem(agent_id="fitness", text="ran 5 km", amount=5, unit="km")],
            events=[
                Event(agent_id="career", title="Interview", due_on=due),
                Event(agent_id="health", title="Clinic", due_on=due, stored=False),
            ],
        )

    monkeypatch.setattr(tracking_routes, "analyze_turn", fake)
    res = client.post("/api/capture", json={"text": "Ran 5 km, interview Thursday"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert [c["text"] for c in body["checkins"]] == ["ran 5 km"]
    assert body["followups"] == [
        {"agent_id": "career", "title": "Interview", "due_on": due.isoformat(), "ends_on": None}
    ]
    assert body["held_back"] == 1
    assert client.get("/api/checkins").json() == []


def test_manual_checkin_is_saved_and_sensitive_text_refused(client):
    ok = client.post("/api/checkins", json={"agent_id": "fitness", "text": "Walked 30 minutes"})
    assert ok.status_code in (200, 201), ok.text
    bad = client.post(
        "/api/checkins",
        json={"agent_id": "fitness", "text": "My HIV test result came back"},
    )
    assert bad.status_code == 422


# --- templates ---------------------------------------------------------------------------


def test_templates_round_trip(client):
    made = client.post(
        "/api/templates",
        json={"title": "Weekly review", "body": "Review my week: {wins}", "agent_id": "career"},
    )
    assert made.status_code == 201, made.text
    tid = made.json()["id"]
    client.post("/api/templates", json={"title": "Any", "body": "Hello {name}"})
    assert len(client.get("/api/templates", params={"agent_id": "career"}).json()) == 2
    assert len(client.get("/api/templates", params={"agent_id": "finance"}).json()) == 1
    upd = client.put(f"/api/templates/{tid}", json={"title": "Review", "body": "x"})
    assert upd.json()["title"] == "Review"
    assert (
        client.post(
            "/api/templates", json={"title": "a", "body": "b", "agent_id": "nope"}
        ).status_code
        == 422
    )
    assert client.delete(f"/api/templates/{tid}").status_code == 204
    assert client.delete(f"/api/templates/{tid}").status_code == 404


# --- organising chats --------------------------------------------------------------------


def test_pin_folder_and_tag_a_chat(client):
    a = client.post("/api/agents/career/chat", json={"message": "Hello"}).json()["conversation_id"]
    b = client.post("/api/agents/career/chat", json={"message": "Again"}).json()["conversation_id"]
    res = client.patch(
        f"/api/conversations/{a}/organise",
        json={"pinned": True, "folder": "Job hunt", "tags": ["cv", "cv", "Urgent"]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["pinned_at"] is not None
    listed = client.get("/api/conversations").json()
    assert listed[0]["id"] == a
    assert [
        c["id"] for c in client.get("/api/conversations", params={"folder": "Job hunt"}).json()
    ] == [a]
    assert [c["id"] for c in client.get("/api/conversations", params={"folder": ""}).json()] == [b]
    assert [c["id"] for c in client.get("/api/conversations", params={"tag": "cv"}).json()] == [a]
    shelves = client.get("/api/conversations/shelves").json()
    assert shelves["folders"] == [{"name": "Job hunt", "count": 1}]
    assert {"name": "cv", "count": 1} in shelves["tags"]
    assert (
        client.patch(f"/api/conversations/{a}/organise", json={"pinned": False}).json()["pinned_at"]
        is None
    )


# --- dialect and spoken replies ----------------------------------------------------------


def test_dialect_and_spoken_rules_reach_the_prompt(client):
    assert (
        client.patch("/api/users/me", json={"reply_dialect": "egyptian"}).json()["reply_dialect"]
        == "egyptian"
    )
    assert client.patch("/api/users/me", json={"reply_dialect": "klingon"}).status_code == 422
    seen = {}
    real = context_module.build_context

    def spy(**kwargs):
        seen.update(dialect=kwargs.get("dialect"), spoken=kwargs.get("spoken"))
        return real(**kwargs)

    import app.agents.runtime as runtime_module

    original = runtime_module.build_context
    runtime_module.build_context = spy
    try:
        client.post("/api/agents/modeer/chat", json={"message": "Hi", "spoken": True})
    finally:
        runtime_module.build_context = original
    assert seen == {"dialect": "egyptian", "spoken": True}
    assert "العامية المصرية" in context_module._DIALECTS["egyptian"]


def test_speak_reports_when_natural_voices_are_off(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "tts_enabled", False)
    assert client.get("/api/voice").json()["speak"] is False
    res = client.post("/api/voice/speak", json={"text": "Hello", "language": "en"})
    assert res.status_code == 503


# --- the CV builder ----------------------------------------------------------------------

CV = {
    "title": "Product CV",
    "target_role": "Product manager",
    "data": {
        "name": "Sara Ali",
        "headline": "Product manager",
        "email": "sara@example.com",
        "summary": "Seven years shipping consumer apps.",
        "experience": [
            {
                "title": "PM",
                "organisation": "Acme",
                "start": "2020",
                "end": "Now",
                "bullets": ["Grew weekly users 40% in a year", "  "],
            }
        ],
        "skills": ["Roadmaps", "SQL"],
    },
}


def test_cv_versions_and_word_export(client):
    made = client.post("/api/cv", json=CV)
    assert made.status_code == 201, made.text
    cv = made.json()
    assert cv["data"]["experience"][0]["bullets"] == ["Grew weekly users 40% in a year"]
    copy = client.post(
        f"/api/cv/{cv['id']}/copy", json={"title": "Data CV", "target_role": "Analyst"}
    )
    assert copy.status_code == 201
    assert copy.json()["data"]["name"] == "Sara Ali"
    assert len(client.get("/api/cv").json()) == 2

    doc = client.get(f"/api/cv/{cv['id']}/docx")
    assert doc.status_code == 200
    assert doc.headers["content-type"].startswith("application/vnd.openxmlformats")
    with zipfile.ZipFile(io.BytesIO(doc.content)) as z:
        xml = z.read("word/document.xml").decode()
        assert "[Content_Types].xml" in z.namelist()
    assert "Sara Ali" in xml and "Grew weekly users 40% in a year" in xml
    assert "<w:bidi/>" not in xml

    too_many = dict(CV, data=dict(CV["data"], experience=[{"bullets": ["x"] * 9}]))
    assert client.post("/api/cv", json=too_many).status_code == 422
    assert client.delete(f"/api/cv/{cv['id']}").status_code == 204
    assert client.get(f"/api/cv/{cv['id']}").status_code == 404


def test_arabic_cv_runs_right_to_left(client):
    body = dict(CV, data=dict(CV["data"], name="سارة علي", summary="مديرة منتجات"))
    cv = client.post("/api/cv", json=body).json()
    with zipfile.ZipFile(io.BytesIO(client.get(f"/api/cv/{cv['id']}/docx").content)) as z:
        xml = z.read("word/document.xml").decode()
    assert "<w:bidi/>" in xml and "الخبرة" in xml
    assert "Roadmaps، SQL" in xml  # lists use the Arabic comma


# --- importing from another assistant ----------------------------------------------------


def test_import_previews_then_saves_only_what_was_ticked(client, monkeypatch):
    async def fake(text, **_):
        return TurnAnalysis(
            facts=[
                _fact("job_title", "Product manager"),
                _fact("city", "Cairo", category="personal"),
                _fact("guess", "Maybe likes jazz", confidence=0.2),
                _fact("pref", "Short answers", scope="agent"),
            ]
        )

    monkeypatch.setattr(memory_routes, "analyze_turn", fake)
    preview = client.post(
        "/api/memory/import/preview", json={"text": "I am a product manager living in Cairo."}
    )
    assert preview.status_code == 200, preview.text
    keys = [f["key"] for f in preview.json()["facts"]]
    assert keys == ["job_title", "city"]
    assert client.get("/api/memory/shared").json() == []

    saved = client.post(
        "/api/memory/import/apply",
        json={"facts": [{"category": "work", "key": "job_title", "value": "Product manager"}]},
    )
    assert saved.json() == {"saved": 1}
    shared = client.get("/api/memory/shared").json()
    assert [(m["key"], m["source"]) for m in shared] == [("job_title", "user")]
