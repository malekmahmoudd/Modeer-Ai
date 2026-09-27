"""Design tools persist independently of AI context and respect ownership."""

import hashlib

from app.agents.context import build_context
from app.agents.registry import require_agent
from app.db.models import Conversation, Document, DocumentChunk, Message
from app.documents.retrieval import Hit


def reply(db, user, *, incognito=False, meta=None):
    c = Conversation(user_id=user.id, agent_id="study", incognito=incognito)
    db.add(c)
    db.flush()
    db.add(Message(conversation_id=c.id, role="user", content="help"))
    m = Message(conversation_id=c.id, role="assistant", content="Existing answer", meta=meta or {})
    db.add(m)
    db.commit()
    return c, m, f"/api/conversations/{c.id}/messages/{m.id}"


def test_preferences_merge_validate_export_and_never_enter_context(client, user):
    r = client.patch("/api/users/me", json={"ui_preferences": {"front_desk": ["travel", "study"]}})
    assert r.status_code == 200
    r = client.patch("/api/users/me", json={"ui_preferences": {"reading_size": 22}})
    assert r.json()["ui_preferences"] == {"front_desk": ["travel", "study"], "reading_size": 22}
    for value in (
        {"front_desk": ["modeer"]},
        {"front_desk": ["study", "study"]},
        {"reading_size": 30},
        {"reading_spacing": 0},
        {"reading_width": 100},
    ):
        assert client.patch("/api/users/me", json={"ui_preferences": value}).status_code == 422
    exported = client.get("/api/users/me/export").json()
    assert exported["account"]["ui_preferences"]["reading_size"] == 22
    user.ui_preferences = {"front_desk": ["NEVER_SEND_PREFERENCES"]}
    packet = build_context(
        agent=require_agent("study"),
        user=user,
        shared=[],
        agent_memory=[],
        goals=[],
        history=[],
        user_message="hello",
    )
    assert "NEVER_SEND_PREFERENCES" not in packet.system


def test_excerpts_ownership_incognito_export_and_rewind(client, db, user, make_user):
    c, m, url = reply(db, user)
    data = {"excerpts": ["A useful excerpt"]}
    assert client.patch(url + "/design", json=data).json() == data
    assert client.get("/api/conversations/excerpts").json()[0]["excerpts"] == data["excerpts"]
    other = make_user("other")
    assert (
        client.patch(url + "/design", json=data, headers={"X-User-Id": other.id}).status_code == 404
    )
    assert client.get("/api/conversations/excerpts", headers={"X-User-Id": other.id}).json() == []
    assert (
        client.post(f"/api/conversations/{c.id}/rewind", json={"mode": "regenerate"}).status_code
        == 409
    )
    exported = client.get("/api/users/me/export").json()
    assert exported["conversations"][0]["messages"][-1]["design"] == data
    for invalid in ([""], ["x" * 8001], ["x"] * 21):
        assert client.patch(url + "/design", json={"excerpts": invalid}).status_code == 422
    assert client.patch(url + "/design", json={"choice": "unsupported"}).status_code == 422
    _, _, private_url = reply(db, user, incognito=True)
    assert client.patch(private_url + "/design", json=data).status_code == 409
    assert client.patch(url + "/design", json={"excerpts": []}).status_code == 200
    assert client.get("/api/conversations/excerpts").json() == []


def test_comparison_notes_merge_without_entering_history(client, db, user):
    c, m, url = reply(db, user, meta={"team": [{"agent_id": "career", "conversation_id": "old"}]})
    assert client.patch(url + "/design", json={"choice": "NEVER_SEND_CHOICE"}).status_code == 200
    assert (
        client.patch(url + "/design", json={"excerpts": ["saved"]}).json()["choice"]
        == "NEVER_SEND_CHOICE"
    )
    db.expire_all()
    packet = build_context(
        agent=require_agent("study"),
        user=user,
        shared=[],
        agent_memory=[],
        goals=[],
        history=[m],
        user_message="next",
    )
    assert "NEVER_SEND_CHOICE" not in packet.system + str(packet.messages)


def test_exact_source_prefix_owner_changed_deleted_and_legacy(client, db, user, make_user):
    source = "The exact retrieved passage. This tail was not sent."
    sent = source[:28]
    doc = Document(
        user_id=user.id,
        agent_id="study",
        filename="notes.txt",
        kind="txt",
        size_bytes=len(source),
        sha256="file",
        status="ready",
        chars=len(source),
    )
    doc.chunks = [DocumentChunk(position=0, text=source)]
    db.add(doc)
    db.flush()
    ref = {
        "label": "D1",
        "document_id": doc.id,
        "filename": doc.filename,
        "chunk_id": doc.chunks[0].id,
        "chars": len(sent),
        "sha256": hashlib.sha256(sent.encode()).hexdigest(),
    }
    _, _, url = reply(db, user, meta={"context": {"documents": [ref]}})
    result = client.get(url + "/sources/D1")
    assert result.status_code == 200 and result.json()["text"] == sent
    other = make_user("stranger")
    assert client.get(url + "/sources/D1", headers={"X-User-Id": other.id}).status_code == 404
    _, _, legacy = reply(db, user, meta={"context": {"documents": [{"label": "D1"}]}})
    assert client.get(legacy + "/sources/D1").status_code == 404
    doc.chunks[0].text = "changed source"
    db.commit()
    assert client.get(url + "/sources/D1").status_code == 409
    db.delete(doc)
    db.commit()
    assert client.get(url + "/sources/D1").status_code == 404


def test_context_receipt_is_a_snapshot_without_document_text(user):
    user.profile = {"location": "Original city"}
    packet = build_context(
        agent=require_agent("study"),
        user=user,
        shared=[],
        agent_memory=[],
        goals=[],
        history=[],
        user_message="hello",
        documents=[
            Hit(
                document_id="d",
                filename="x",
                heading=None,
                page=None,
                text="PRIVATE_SOURCE_TEXT",
                score=1,
                label="D1",
                chunk_id="chunk",
            )
        ],
    )
    user.profile = {"location": "New city"}
    receipt = str(packet.diagnostics["receipt"])
    assert "Original city" in receipt and "New city" not in receipt
    assert "PRIVATE_SOURCE_TEXT" not in str(packet.diagnostics)
    assert packet.diagnostics["documents"][0]["chunk_id"] == "chunk"
    for section in packet.diagnostics["receipt"]:
        assert section["text"] in packet.system
