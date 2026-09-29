"""Regression tests for the review of the twelve-feature batch: reminders end
with the device's sign-in, every plan step due today is in the digest, a quick
note saves once, and a CV's Word file is always valid XML."""

from __future__ import annotations

import asyncio
import io
import json
import os
import uuid
import zipfile
from datetime import date, datetime, timedelta
from xml.etree import ElementTree

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

from app.core.config import settings
from app.core.passwords import hash_password
from app.cv.docx import render
from app.cv.schemas import CvData
from app.db.base import utcnow
from app.db.models import (
    CaptureReceipt,
    CheckIn,
    CvDocument,
    FollowUp,
    Plan,
    PlanStep,
    PushSubscription,
    User,
    UserSession,
)
from app.push import service, webpush
from app.tracking import service as tracking_service

PASSWORD = "correct horse battery staple"
FCM = "https://fcm.googleapis.com/fcm/send/"


# --- reminders belong to a signed-in device --------------------------------------------


@pytest.fixture
def accounts(db, monkeypatch):
    sam = User(display_name="Sam", email="sam@example.com", password_hash=hash_password(PASSWORD))
    kim = User(display_name="Kim", email="kim@example.com", password_hash=hash_password(PASSWORD))
    db.add_all([sam, kim])
    db.commit()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_access_keys", {})
    return sam, kim


def _origin():
    return {"Origin": settings.frontend_url}


def _login(client, email="sam@example.com"):
    client.cookies.clear()
    r = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}, headers=_origin()
    )
    assert r.status_code == 200, r.text


def _keys():
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return {"p256dh": webpush.b64url(public), "auth": webpush.b64url(os.urandom(16))}


def _subscribe(client, endpoint):
    r = client.post(
        "/api/push/subscribe", json={"endpoint": endpoint, "keys": _keys()}, headers=_origin()
    )
    assert r.status_code == 201, r.text


def _device_on(client, endpoint) -> bool:
    r = client.post("/api/push/device", json={"endpoint": endpoint}, headers=_origin())
    assert r.status_code == 200, r.text
    return r.json()["on"]


class _Recorder:
    """Stands in for httpx.AsyncClient; records where reminders went."""

    sent: list[str] = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, content, headers):
        _Recorder.sent.append(url)

        class R:
            status_code = 201

        return R()


def _send(db, user, monkeypatch) -> list[str]:
    _Recorder.sent = []
    monkeypatch.setattr(service.httpx, "AsyncClient", _Recorder)
    db.expire_all()
    asyncio.run(service.send(db, db.get(User, user.id), {"title": "t", "body": "b", "url": "/"}))
    db.commit()
    return list(_Recorder.sent)


def _count(db, endpoint) -> int:
    db.expire_all()
    return db.scalar(
        select(func.count())
        .select_from(PushSubscription)
        .where(PushSubscription.endpoint == endpoint)
    )


def test_signing_out_ends_this_devices_reminders(client, db, accounts, monkeypatch):
    sam, _ = accounts
    endpoint = FCM + "logout"
    _login(client)
    _subscribe(client, endpoint)
    assert _device_on(client, endpoint)
    assert _send(db, sam, monkeypatch) == [endpoint]
    client.post("/api/auth/logout", headers=_origin())
    assert _count(db, endpoint) == 0
    assert _send(db, sam, monkeypatch) == []


def test_removing_a_device_remotely_ends_its_reminders(client, db, accounts, monkeypatch):
    sam, _ = accounts
    lost = FCM + "lost-phone"
    _login(client)
    _subscribe(client, lost)
    db.expire_all()
    lost_session = db.scalar(
        select(PushSubscription.session_id).where(PushSubscription.endpoint == lost)
    )
    _login(client)  # the laptop
    r = client.delete(f"/api/auth/sessions/{lost_session}", headers=_origin())
    assert r.status_code in (200, 204), r.text
    assert _count(db, lost) == 0
    assert _send(db, sam, monkeypatch) == []


def test_sign_out_everywhere_ends_every_devices_reminders(client, db, accounts, monkeypatch):
    sam, _ = accounts
    phone, laptop = FCM + "phone", FCM + "laptop"
    _login(client)
    _subscribe(client, phone)
    _login(client)
    _subscribe(client, laptop)
    assert sorted(_send(db, sam, monkeypatch)) == sorted([phone, laptop])
    r = client.post("/api/auth/sign-out-everywhere", headers=_origin())
    assert r.status_code == 200, r.text
    assert _count(db, phone) == 0 and _count(db, laptop) == 0
    assert _send(db, sam, monkeypatch) == []


def test_revoked_session_is_checked_again_before_sending(client, db, accounts, monkeypatch):
    """Even if a subscription row survives (a revocation path that forgot to
    delete it), nothing goes to a device that was signed out."""
    sam, _ = accounts
    endpoint = FCM + "survivor"
    _login(client)
    _subscribe(client, endpoint)
    db.expire_all()
    sub = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    db.get(UserSession, sub.session_id).revoked_at = utcnow().replace(tzinfo=None)
    db.commit()
    assert _send(db, sam, monkeypatch) == []
    assert _count(db, endpoint) == 0


def test_another_account_on_the_same_browser_does_not_inherit_reminders(
    client, db, accounts, monkeypatch
):
    sam, kim = accounts
    endpoint = FCM + "shared-laptop"
    _login(client, "sam@example.com")
    _subscribe(client, endpoint)
    _login(client, "kim@example.com")  # Sam did not sign out; Kim signs in
    assert not _device_on(client, endpoint)
    assert _send(db, kim, monkeypatch) == []
    # Kim turns them on: the browser is now Kim's, and Sam's reminders stop.
    _subscribe(client, endpoint)
    assert _device_on(client, endpoint)
    assert _send(db, kim, monkeypatch) == [endpoint]
    assert _send(db, sam, monkeypatch) == []


def test_an_expired_sign_in_pauses_and_the_same_account_carries_it_over(
    client, db, accounts, monkeypatch
):
    sam, kim = accounts
    endpoint = FCM + "weekly"
    _login(client)
    _subscribe(client, endpoint)
    db.expire_all()
    sub = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    db.get(UserSession, sub.session_id).expires_at = utcnow().replace(tzinfo=None) - timedelta(
        minutes=1
    )
    db.commit()
    assert _send(db, sam, monkeypatch) == []  # paused, not deleted
    assert _count(db, endpoint) == 1
    _login(client, "kim@example.com")
    assert not _device_on(client, endpoint)  # never to another account
    _login(client, "sam@example.com")
    assert _device_on(client, endpoint)
    assert _send(db, sam, monkeypatch) == [endpoint]


def test_a_password_change_keeps_this_device_and_ends_the_others(client, db, accounts, monkeypatch):
    sam, _ = accounts
    other, this = FCM + "other-device", FCM + "this-device"
    _login(client)
    _subscribe(client, other)
    _login(client)
    _subscribe(client, this)
    r = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "another long password 42"},
        headers=_origin(),
    )
    assert r.status_code == 200, r.text
    assert _count(db, other) == 0
    assert _device_on(client, this)
    assert _send(db, sam, monkeypatch) == [this]


def test_subscribing_needs_a_device_sign_in_when_accounts_are_on(client, db, accounts):
    # A cookie from before devices were tracked names no device: refuse, so the
    # subscription can always be ended with a sign-out.
    from app.core.auth import COOKIE, sign_session

    sam, _ = accounts
    client.cookies.clear()
    client.cookies.set(COOKIE, sign_session(sam.id, sam.session_epoch or 0, None), path="/api")
    r = client.post(
        "/api/push/subscribe", json={"endpoint": FCM + "legacy", "keys": _keys()}, headers=_origin()
    )
    assert r.status_code == 409


def test_legacy_subscriptions_without_a_device_are_never_sent_to(db, accounts, monkeypatch):
    sam, _ = accounts
    k = _keys()
    db.add(
        PushSubscription(user_id=sam.id, endpoint=FCM + "old", p256dh=k["p256dh"], auth=k["auth"])
    )
    db.commit()
    assert _send(db, sam, monkeypatch) == []
    assert _count(db, FCM + "old") == 0


# --- the digest lists every step due today ---------------------------------------------


def test_digest_lists_every_unfinished_step_due_today(db, user):
    today = date(2026, 9, 28)
    plan = Plan(user_id=user.id, agent_id="study", title="Revision", starts_on=today)
    plan.steps = [
        PlanStep(position=1, text="Overdue reading", due_on=today - timedelta(days=2)),
        PlanStep(position=2, text="Past paper A", due_on=today),
        PlanStep(position=3, text="Past paper B", due_on=today),
        PlanStep(position=4, text="Done already", due_on=today, done_at=datetime(2026, 9, 28, 7)),
        PlanStep(position=5, text="Next week", due_on=today + timedelta(days=7)),
    ]
    other = User(display_name="Other")
    db.add_all([plan, other])
    db.flush()
    db.add(
        Plan(
            user_id=other.id,
            agent_id="study",
            title="Theirs",
            starts_on=today,
            steps=[PlanStep(position=1, text="Not yours", due_on=today)],
        )
    )
    db.commit()
    _, body, count = service.digest(db, user, today)
    assert count == 2
    assert "Past paper A" in body and "Past paper B" in body
    assert "Overdue" not in body and "Done already" not in body and "Not yours" not in body


def test_digest_stays_short_and_hides_details_when_asked(db, user):
    today = date(2026, 9, 28)
    for i in range(6):
        db.add(FollowUp(user_id=user.id, agent_id="career", title=f"Thing {i}", due_on=today))
    db.commit()
    _, body, count = service.digest(db, user, today)
    assert count == 6 and len(body.splitlines()) == 5 and body.endswith("+2 more")
    user.ui_preferences = {"push_details": False}
    db.commit()
    _, body, _ = service.digest(db, user, today)
    assert body == "You have 6 things today." and "Thing" not in body


# --- a quick note saves once ------------------------------------------------------------


def _note(key=None, **extra):
    due = (date.today() + timedelta(days=3)).isoformat()
    body = {
        "key": key or uuid.uuid4().hex,
        "checkins": [{"agent_id": "fitness", "text": "Ran 5 km"}],
        "followups": [{"agent_id": "career", "title": "Interview", "due_on": due}],
    }
    body.update(extra)
    return body


def test_a_retried_quick_note_is_not_saved_twice(client, db, user):
    note = _note()
    first = client.post("/api/capture/save", json=note)
    assert first.status_code == 200, first.text
    again = client.post("/api/capture/save", json=note)  # the first response was "lost"
    assert again.status_code == 200 and again.json() == first.json()
    db.expire_all()
    assert (
        db.scalar(select(func.count()).select_from(CheckIn).where(CheckIn.user_id == user.id)) == 1
    )
    assert (
        db.scalar(select(func.count()).select_from(FollowUp).where(FollowUp.user_id == user.id))
        == 1
    )


def test_one_bad_item_saves_nothing_and_a_fixed_retry_saves_all(client, db, user):
    key = uuid.uuid4().hex
    bad = _note(
        key, followups=[{"agent_id": "nobody", "title": "Interview", "due_on": "2026-10-01"}]
    )
    assert client.post("/api/capture/save", json=bad).status_code == 404
    db.expire_all()
    assert (
        db.scalar(select(func.count()).select_from(CheckIn).where(CheckIn.user_id == user.id)) == 0
    )
    assert client.post("/api/capture/save", json=_note(key)).status_code == 200
    db.expire_all()
    assert (
        db.scalar(select(func.count()).select_from(CheckIn).where(CheckIn.user_id == user.id)) == 1
    )


def test_the_same_key_with_different_items_is_refused(client):
    key = uuid.uuid4().hex
    assert client.post("/api/capture/save", json=_note(key)).status_code == 200
    changed = _note(key, checkins=[{"agent_id": "fitness", "text": "Swam 1 km"}])
    assert client.post("/api/capture/save", json=changed).status_code == 409


def test_quick_note_keeps_the_sensitive_data_rule(client, db, user):
    note = _note(checkins=[{"agent_id": "fitness", "text": "My HIV test result came back"}])
    assert client.post("/api/capture/save", json=note).status_code == 422
    db.expire_all()
    assert (
        db.scalar(select(func.count()).select_from(FollowUp).where(FollowUp.user_id == user.id))
        == 0
    )


def test_a_receipt_keeps_no_text_and_deleting_an_item_deletes_its_words(client, db, user):
    note = _note(
        checkins=[{"agent_id": "fitness", "text": "Walked the Corniche 7 km"}],
        followups=[
            {
                "agent_id": "career",
                "title": "Call Dr Hanan about results",
                "due_on": (date.today() + timedelta(days=2)).isoformat(),
            }
        ],
    )
    first = client.post("/api/capture/save", json=note).json()
    db.expire_all()
    receipt = db.scalar(select(CaptureReceipt).where(CaptureReceipt.key == note["key"]))
    stored = json.dumps(receipt.result) + receipt.fingerprint
    for words in ("Corniche", "Hanan", "Walked", "results"):
        assert words not in stored
    assert receipt.result == {
        "checkins": [first["checkins"][0]["id"]],
        "followups": [first["followups"][0]["id"]],
    }

    # The person deletes the check-in: its words exist nowhere any more, and a
    # late retry neither brings it back nor saves it again.
    checkin_id = first["checkins"][0]["id"]
    assert client.delete(f"/api/checkins/{checkin_id}").status_code == 204
    again = client.post("/api/capture/save", json=note)
    assert again.status_code == 200
    assert again.json()["checkins"] == []
    assert [f["title"] for f in again.json()["followups"]] == ["Call Dr Hanan about results"]
    db.expire_all()
    assert (
        db.scalar(select(func.count()).select_from(CheckIn).where(CheckIn.user_id == user.id)) == 0
    )
    for result, fingerprint in db.execute(
        select(CaptureReceipt.result, CaptureReceipt.fingerprint)
    ):
        assert "Corniche" not in json.dumps(result) + fingerprint


def test_quick_note_receipts_are_forgotten_after_a_day(client, db, user):
    old_key, new_key = uuid.uuid4().hex, uuid.uuid4().hex
    assert client.post("/api/capture/save", json=_note(old_key)).status_code == 200
    db.expire_all()
    db.scalar(select(CaptureReceipt).where(CaptureReceipt.key == old_key)).created_at = (
        utcnow() - timedelta(hours=25)
    )
    db.commit()
    assert client.post("/api/capture/save", json=_note(new_key)).status_code == 200
    assert tracking_service.sweep_capture_receipts(db) == 1
    db.commit()
    keys = set(db.scalars(select(CaptureReceipt.key)))
    assert keys == {new_key}


def test_account_deletion_removes_receipts(client, db, user):
    assert client.post("/api/capture/save", json=_note()).status_code == 200
    user_id = user.id
    db.delete(db.get(User, user_id))
    db.commit()
    assert (
        db.scalar(
            select(func.count())
            .select_from(CaptureReceipt)
            .where(CaptureReceipt.user_id == user_id)
        )
        == 0
    )


# --- Word files are valid XML ------------------------------------------------------------


def _document_xml(data: CvData) -> str:
    with zipfile.ZipFile(io.BytesIO(render(data))) as z:
        return z.read("word/document.xml").decode()


def test_word_export_drops_characters_xml_cannot_hold():
    data = CvData(
        name="Sara\x0bAli\x00",
        headline="R&D <lead> \"quotes\" 'apos'",
        summary="سارة علي تدير المنتجات 😀 𝔘𝔫𝔦𝔠𝔬𝔡𝔢\ttab\nline￾",
        skills=["SQL\x1f", "Roadmaps"],
    )
    assert data.name == "SaraAli"
    xml = _document_xml(data)
    ElementTree.fromstring(xml)  # raises on any invalid character
    assert "SaraAli" in xml and "R&amp;D &lt;lead&gt;" in xml
    assert "سارة علي" in xml and "😀" in xml and "𝔘𝔫𝔦𝔠𝔬𝔡𝔢" in xml and "\ttab" in xml


def test_a_cv_stored_before_the_fix_still_exports_valid_xml(client, db, user):
    # Written straight to the database, the way an older CV could be.
    row = CvDocument(
        user_id=user.id, title="Old\x0b", data={"name": "Bad\x0bName", "skills": ["A\x01"]}
    )
    db.add(row)
    db.commit()
    r = client.get(f"/api/cv/{row.id}/docx")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read("word/document.xml").decode()
    ElementTree.fromstring(xml)
    assert "BadName" in xml
    assert client.get(f"/api/cv/{row.id}").json()["data"]["name"] == "BadName"


def test_saving_a_cv_removes_invalid_characters(client):
    made = client.post("/api/cv", json={"title": "CV\x0b", "data": {"name": "A\x0bB"}})
    assert made.status_code == 201, made.text
    assert made.json()["title"] == "CV" and made.json()["data"]["name"] == "AB"


# --- on PostgreSQL too (set RECOVERY_TEST_POSTGRES_URL; SQLite otherwise) ------------


@pytest.fixture
def scratch_engine(tmp_path):
    """A throwaway database: its own schema on PostgreSQL, or a SQLite file."""
    import os

    from sqlalchemy import create_engine, text

    from app.db.base import Base

    url = os.environ.get("RECOVERY_TEST_POSTGRES_URL")
    schema = "review_fixes_" + uuid.uuid4().hex
    if url:
        admin = create_engine(url)
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'scratch.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    if url:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.parametrize("same_items", [True, False])
def test_simultaneous_saves_of_one_note_store_it_once(scratch_engine, monkeypatch, same_items):
    """Two saves with the same key arrive together (a double tap, or a retry
    racing the original): both look, find no receipt, and write. One wins; the
    other returns the winner's result (same items) or is refused (different
    items). The items are stored once either way."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException
    from sqlalchemy.orm import Session

    from app.api.routes import tracking

    with Session(scratch_engine) as db:
        person = User(display_name="Racer")
        db.add(person)
        db.commit()
        person_id = person.id

    barrier = threading.Barrier(2)
    local = threading.local()
    original = tracking._receipt

    def overlap(db, user_id, key):
        found = original(db, user_id, key)
        if not getattr(local, "met", False):
            local.met = True
            barrier.wait(timeout=10)  # both have looked before either writes
        return found

    monkeypatch.setattr(tracking, "_receipt", overlap)
    key = uuid.uuid4().hex

    def save(index):
        body = _note(key)
        if not same_items and index:
            body["checkins"] = [{"agent_id": "fitness", "text": "Rowed 3 km"}]
        with Session(scratch_engine) as db:
            try:
                result = tracking.save_capture(
                    tracking.CaptureSave(**body), db.get(User, person_id), db
                )
                db.commit()
                return 200, result
            except HTTPException as exc:
                db.rollback()
                return exc.status_code, None

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(save, [0, 1]))

    statuses = sorted(status for status, _ in outcomes)
    with Session(scratch_engine) as db:
        checkins = db.scalar(select(func.count()).select_from(CheckIn))
        followups = db.scalar(select(func.count()).select_from(FollowUp))
        receipts = db.scalar(select(func.count()).select_from(CaptureReceipt))
    assert (checkins, followups, receipts) == (1, 1, 1)
    if same_items:
        assert statuses == [200, 200]
        assert outcomes[0][1] == outcomes[1][1]
    else:
        assert statuses == [200, 409]


def test_signed_out_sessions_take_their_subscriptions_with_them(scratch_engine):
    """The database enforces it too: deleting a device row (the 30-day sweep)
    removes its subscriptions. SQLite enforces foreign keys only when asked,
    so there the app deletes them itself (checked above); this runs the
    database's own cascade on PostgreSQL."""
    from sqlalchemy.orm import Session

    if scratch_engine.dialect.name != "postgresql":
        pytest.skip("foreign-key cascade is checked on PostgreSQL")
    with Session(scratch_engine) as db:
        person = User(display_name="Gone")
        db.add(person)
        db.flush()
        device = UserSession(user_id=person.id, epoch=0, expires_at=utcnow().replace(tzinfo=None))
        db.add(device)
        db.flush()
        k = _keys()
        db.add(
            PushSubscription(
                user_id=person.id,
                endpoint=FCM + "cascade",
                p256dh=k["p256dh"],
                auth=k["auth"],
                session_id=device.id,
            )
        )
        db.commit()
        db.delete(device)
        db.commit()
        assert db.scalar(select(func.count()).select_from(PushSubscription)) == 0


def test_receipt_sweep_compares_times_correctly(scratch_engine):
    from sqlalchemy.orm import Session

    with Session(scratch_engine) as db:
        person = User(display_name="Sweep")
        db.add(person)
        db.flush()
        now = utcnow()
        db.add_all(
            [
                CaptureReceipt(
                    user_id=person.id,
                    key="old" + "0" * 10,
                    fingerprint="f",
                    result={},
                    created_at=now - timedelta(hours=25),
                ),
                CaptureReceipt(
                    user_id=person.id,
                    key="new" + "0" * 10,
                    fingerprint="f",
                    result={},
                    created_at=now - timedelta(hours=23),
                ),
            ]
        )
        db.commit()
        assert tracking_service.sweep_capture_receipts(db, now=now) == 1
        db.commit()
        assert list(db.scalars(select(CaptureReceipt.key))) == ["new" + "0" * 10]
