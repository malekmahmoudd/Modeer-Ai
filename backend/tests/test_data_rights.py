"""Export and erasure.

Modeer stores what someone tells it about their health, money and career. These
tests exist because "we support deletion" is worth nothing unless the rows
actually go, and because an export that quietly omits the message bodies is a
summary of someone's data rather than their data.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select

from app.core.config import settings
from app.db.models import (
    AgentMemory,
    Conversation,
    Goal,
    Message,
    SharedMemory,
    UsageBucket,
    User,
)


def _enable_auth(monkeypatch, users):
    keys = {u.id: hashlib.sha256(k.encode()).hexdigest() for u, k in users}
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_access_keys", keys)


def _populate(client, origin) -> str:
    """Give the signed-in account a conversation, a memory and a goal."""
    client.post("/api/goals", json={"title": "Finish the CV"}, headers=origin)
    client.post(
        "/api/memory/shared",
        json={"category": "career", "key": "role", "value": "staff engineer"},
        headers=origin,
    )
    reply = client.post(
        "/api/agents/study/chat",
        json={"message": "I have a thermodynamics final on the 20th."},
        headers=origin,
    )
    assert reply.status_code == 200, reply.text
    return reply.json()["conversation_id"]


def test_export_contains_the_whole_account_including_message_text(
    client, make_user, monkeypatch, db
):
    alice = make_user("Alice")
    _enable_auth(monkeypatch, [(alice, "a" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    _populate(client, origin)

    response = client.get("/api/users/me/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"

    data = response.json()
    assert data["account"]["id"] == alice.id
    assert data["format"] == "modeer-export-1"
    assert data["goals"] and data["goals"][0]["title"] == "Finish the CV"
    assert data["shared_memories"] and data["shared_memories"][0]["value"] == "staff engineer"

    # The transcript must carry the actual words, not just a count.
    messages = [m for c in data["conversations"] for m in c["messages"]]
    assert any("thermodynamics" in m["content"] for m in messages if m["role"] == "user")
    assert any(m["role"] == "assistant" and m["content"] for m in messages)


def test_export_is_scoped_to_the_signed_in_account(client, make_user, monkeypatch):
    alice, bob = make_user("Alice"), make_user("Bob")
    _enable_auth(monkeypatch, [(alice, "a" * 40), (bob, "b" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    _populate(client, origin)

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"access_key": "b" * 40}, headers=origin)
    data = client.get("/api/users/me/export").json()
    assert data["account"]["id"] == bob.id
    assert data["conversations"] == []
    assert data["goals"] == []
    assert data["shared_memories"] == []


def test_deleting_the_account_erases_every_row_it_owns(client, make_user, monkeypatch, db):
    alice, bob = make_user("Alice"), make_user("Bob")
    alice_id, bob_id = alice.id, bob.id
    _enable_auth(monkeypatch, [(alice, "a" * 40), (bob, "b" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    _populate(client, origin)

    # The usage ledger has no foreign key to users, so it is the row most likely
    # to survive a deletion and keep a record of when this person used Modeer.
    db.add(UsageBucket(account=alice_id, kind="requests", window=1, amount=3))
    db.add(UsageBucket(account=bob_id, kind="requests", window=1, amount=5))
    db.commit()

    response = client.post("/api/users/me/delete", json={"confirm": "DELETE"}, headers=origin)
    assert response.status_code == 204
    # The request used its own session; detach this one's cached copies so the
    # assertions below read the database rather than the identity map.
    db.expunge_all()

    for model in (Conversation, SharedMemory, AgentMemory, Goal):
        remaining = db.scalar(
            select(func.count()).select_from(model).where(model.user_id == alice_id)
        )
        assert remaining == 0, f"{model.__name__} rows survived deletion"
    assert db.get(User, alice_id) is None
    assert (
        db.scalar(
            select(func.count())
            .select_from(Message)
            .join(Conversation)
            .where(Conversation.user_id == alice_id)
        )
        == 0
    )
    assert (
        db.scalar(
            select(func.count()).select_from(UsageBucket).where(UsageBucket.account == alice_id)
        )
        == 0
    ), "usage ledger survived account deletion"

    # Someone else's data is untouched.
    assert (
        db.scalar(
            select(func.count()).select_from(UsageBucket).where(UsageBucket.account == bob_id)
        )
        == 1
    )


def test_deletion_signs_the_session_out(client, make_user, monkeypatch):
    alice = make_user("Alice")
    _enable_auth(monkeypatch, [(alice, "a" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    client.post("/api/users/me/delete", json={"confirm": "DELETE"}, headers=origin)
    assert client.get("/api/goals").status_code == 401


def test_deletion_needs_an_explicit_confirmation(client, make_user, monkeypatch, db):
    alice = make_user("Alice")
    _enable_auth(monkeypatch, [(alice, "a" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)

    assert (
        client.post("/api/users/me/delete", json={"confirm": "yes"}, headers=origin).status_code
        == 422
    )
    assert client.post("/api/users/me/delete", json={}, headers=origin).status_code == 422
    assert db.get(User, alice.id) is not None


def test_a_conversation_can_be_deleted_on_its_own(client, make_user, monkeypatch, db):
    alice = make_user("Alice")
    _enable_auth(monkeypatch, [(alice, "a" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    conversation_id = _populate(client, origin)

    assert client.delete(f"/api/conversations/{conversation_id}", headers=origin).status_code == 204
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404
    db.expire_all()
    assert (
        db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        == 0
    ), "messages outlived their conversation"
    # The account itself survives a conversation deletion.
    assert db.get(User, alice.id) is not None


def test_one_account_cannot_delete_anothers_conversation(client, make_user, monkeypatch):
    alice, bob = make_user("Alice"), make_user("Bob")
    _enable_auth(monkeypatch, [(alice, "a" * 40), (bob, "b" * 40)])
    origin = {"Origin": settings.frontend_url}
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    conversation_id = _populate(client, origin)

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"access_key": "b" * 40}, headers=origin)
    # Indistinguishable from a conversation that does not exist.
    assert client.delete(f"/api/conversations/{conversation_id}", headers=origin).status_code == 404

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"access_key": "a" * 40}, headers=origin)
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 200


def test_privacy_notice_is_readable_without_an_account(client, make_user, monkeypatch):
    """Someone deciding whether to accept an invitation has to read it first."""
    _enable_auth(monkeypatch, [(make_user("Alice"), "a" * 40)])
    response = client.get("/api/legal/privacy")
    assert response.status_code == 200

    body = response.json()
    assert body["format"] == "markdown"
    text = body["content"]
    # The things a person most needs to be told, and would be worst served by
    # us quietly dropping.
    assert "provider" in text.lower()
    assert "delete" in text.lower()
    assert "backup" in text.lower()
    assert "not medical, legal or financial advice" in text.lower()
