"""Reminders on the lock screen: Web Push encryption, subscriptions, the daily
digest, and removing browsers that have gone away."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select

from app.db.models import FollowUp, PushSent, PushSubscription
from app.push import service, webpush
from app.users.service import get_or_create_demo_user

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"


def _sub(endpoint, public, auth):
    keys = {"p256dh": webpush.b64url(public), "auth": webpush.b64url(auth)}
    return {"endpoint": endpoint, "keys": keys}


def _followup(user, title, due_on):
    return FollowUp(user_id=user.id, agent_id="career", title=title, due_on=due_on)


def test_encryption_matches_the_rfc_8291_example():
    sender = ec.derive_private_key(
        int.from_bytes(webpush.unb64url("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"),
        ec.SECP256R1(),
    )
    body = webpush.encrypt(
        b"When I grow up, I want to be a watermelon",
        webpush.unb64url(
            "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
        ),
        webpush.unb64url("BTBZMqHH6r4Tts7J_aSIgg"),
        sender_key=sender,
        salt=webpush.unb64url("DGv6ra1nlYgDCS1FRnbzlw"),
    )
    assert webpush.b64url(body) == (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYW"
        "AmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgS"
        "xsj_Qulcy4a-fN"
    )


def test_only_real_push_services_are_accepted(client):
    assert webpush.allowed_endpoint(ENDPOINT)
    assert webpush.allowed_endpoint("https://web.push.apple.com/QGuQ")
    assert not webpush.allowed_endpoint("https://evil.example/collect")
    assert not webpush.allowed_endpoint("http://fcm.googleapis.com/x")
    bad = client.post(
        "/api/push/subscribe",
        json={
            "endpoint": "https://169.254.169.254/latest",
            "keys": {"p256dh": "x" * 40, "auth": "y" * 16},
        },
    )
    assert bad.status_code == 422


def _browser():
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return key, public, os.urandom(16)


def test_a_browser_subscribes_and_gets_a_readable_digest(client, db, monkeypatch):
    key, public, auth = _browser()
    public_key = client.get("/api/push/key").json()["public_key"]
    assert len(webpush.unb64url(public_key)) == 65
    made = client.post(
        "/api/push/subscribe",
        json={
            "endpoint": ENDPOINT,
            "keys": {"p256dh": webpush.b64url(public), "auth": webpush.b64url(auth)},
        },
    )
    assert made.status_code == 201
    user = get_or_create_demo_user(db)
    today = date(2026, 9, 28)
    db.add(
        FollowUp(user_id=user.id, agent_id="career", title="Interview at Vodafone", due_on=today)
    )
    db.add(
        FollowUp(
            user_id=user.id, agent_id="study", title="Thermo exam", due_on=today + timedelta(days=1)
        )
    )
    db.commit()

    sent: list[tuple[str, bytes, dict]] = []

    class FakeResponse:
        status_code = 201

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, content, headers):
            sent.append((url, content, headers))
            return FakeResponse()

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeClient)
    import asyncio

    nine = datetime(2026, 9, 28, 9, 0, tzinfo=UTC)
    assert asyncio.run(service.send_due(db, now=nine)) == 1
    url, body, headers = sent[0]
    assert url == ENDPOINT and headers["Content-Encoding"] == "aes128gcm"
    assert headers["Authorization"].startswith("vapid t=")
    text = webpush.decrypt(body, key, auth).decode()
    assert "Today: Interview at Vodafone" in text and "Tomorrow: Thermo exam" in text
    # Once a day.
    assert asyncio.run(service.send_due(db, now=nine + timedelta(hours=1))) == 0
    assert db.scalar(select(PushSent).where(PushSent.user_id == user.id)).kind == "digest"


def test_details_can_be_hidden_from_the_lock_screen(client, db):
    user = get_or_create_demo_user(db)
    user.ui_preferences = {"push_details": False}
    db.add(
        FollowUp(
            user_id=user.id, agent_id="career", title="Private thing", due_on=date(2026, 9, 28)
        )
    )
    db.commit()
    title, body, count = service.digest(db, user, date(2026, 9, 28))
    assert count == 1 and body == "You have 1 thing today." and "Private" not in body


def test_nothing_is_sent_before_the_chosen_hour_or_at_night(db, monkeypatch):
    user = get_or_create_demo_user(db)
    db.add(PushSubscription(user_id=user.id, endpoint=ENDPOINT, p256dh="x" * 87, auth="y" * 22))
    db.commit()
    import asyncio

    for hour in (6, 22):
        at = datetime(2026, 9, 28, hour, 0, tzinfo=UTC)
        assert asyncio.run(service.send_due(db, now=at)) == 0
    assert db.scalar(select(PushSent)) is None


@pytest.mark.parametrize("status", [404, 410])
def test_a_browser_that_has_gone_away_is_forgotten(client, db, monkeypatch, status):
    _, public, auth = _browser()
    client.post(
        "/api/push/subscribe",
        json={
            "endpoint": ENDPOINT,
            "keys": {"p256dh": webpush.b64url(public), "auth": webpush.b64url(auth)},
        },
    )

    class Gone:
        status_code = status

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return Gone()

    monkeypatch.setattr(service.httpx, "AsyncClient", FakeClient)
    assert client.post("/api/push/test").status_code == 409
    assert db.scalar(select(PushSubscription)) is None
