"""Regression coverage for the second independent launch review."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

from app.api.routes import auth
from app.core import passwords
from app.core.auth import COOKIE, session_claims
from app.core.config import settings
from app.db.base import Base
from app.db.models import RecoveryCode, User


@pytest.mark.parametrize("same_code", [True, False])
def test_simultaneous_recovery_is_atomic(tmp_path, monkeypatch, same_code):
    postgres = os.environ.get("RECOVERY_TEST_POSTGRES_URL")
    admin = create_engine(postgres) if postgres else None
    schema = "recovery_test_" + uuid4().hex
    if admin is not None:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = (
        create_engine(postgres, connect_args={"options": f"-csearch_path={schema}"})
        if postgres
        else create_engine(f"sqlite:///{tmp_path / 'race.db'}")
    )
    Base.metadata.create_all(engine)
    codes = ["ABCD-EFGH-JKMP", "QRST-UVWX-Y234"]
    with Session(engine) as db:
        user = User(email="race@example.com", display_name="Race")
        db.add(user)
        db.flush()
        user_id = user.id
        db.add_all(
            [
                RecoveryCode(user_id=user_id, code_hash=passwords.hash_recovery_code(c))
                for c in codes
            ]
        )
        db.commit()
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(settings, "auth_secret", "s" * 40)
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:3000")
    monkeypatch.setattr(auth, "_throttle", lambda *args: None)
    barrier = Barrier(2)
    original = auth._lock_credentials

    def overlap(db, account, request=None):
        # Both requests have read the account before either claims the lock.
        barrier.wait(timeout=10)
        original(db, account, request)

    monkeypatch.setattr(auth, "_lock_credentials", overlap)

    def recover(index):
        with Session(engine) as db:
            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "headers": [(b"origin", b"http://localhost:3000")],
                }
            )
            try:
                response = Response()
                auth.recover(
                    auth.Recover(
                        email="race@example.com",
                        code=codes[0 if same_code else index],
                        new_password=f"new-password-{index}",
                    ),
                    request,
                    response,
                    db,
                )
                cookie = SimpleCookie(response.headers["set-cookie"])
                claims = session_claims(cookie[COOKIE].value)
                assert claims is not None and claims[0] == user_id
                return 200, claims[1]
            except HTTPException as exc:
                return exc.status_code, None

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(recover, [0, 1]))
        assert outcomes == ([(200, 1), (401, None)] if same_code else [(200, 1), (200, 2)])
        with Session(engine) as db:
            assert db.get(User, user_id).session_epoch == (1 if same_code else 2)
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()


def test_profile_limit_applies_to_merged_state(client):
    first = {f"field{i}": "x" * 300 for i in range(20)}
    assert client.patch("/api/users/me", json={"profile": first}).status_code == 200
    result = client.patch("/api/users/me", json={"profile": {"overflow": "value"}})
    assert result.status_code == 422
    assert client.get("/api/users/me").json()["profile"] == first
    assert client.patch("/api/users/me", json={"profile": {"field0": "changed"}}).status_code == 200


def test_legacy_context_is_bounded_without_deleting_records():
    from app.agents.context import _about_user, _goals_block, _memory_block

    value = "x" * 100000
    user = SimpleNamespace(display_name="User", profile={"legacy": value}, onboarded=True)
    row = SimpleNamespace(category="context", key="legacy", value=value)
    goal = SimpleNamespace(status="active", priority=1, title="Goal", detail=value)
    assert len(_about_user(user)) < 6100
    block, used = _memory_block("PERSONAL_CONTEXT", [row])
    assert len(block) < 6100 and used == ["context.legacy"]
    assert len(_goals_block([goal])) < 6100
    assert row.value == value and user.profile["legacy"] == value


def test_goal_detail_write_limit(client):
    response = client.post("/api/goals", json={"title": "Goal", "detail": "x" * 2001})
    assert response.status_code == 422


def test_quality_hash_tracks_content_not_reports(tmp_path):
    from quality_check import source_fingerprint

    (tmp_path / "app").mkdir()
    source = tmp_path / "app" / "prompt.md"
    source.write_text("first")
    for name in ["quality_check.py", "requirements.lock"]:
        (tmp_path / name).write_text("fixture")
    first = source_fingerprint(tmp_path)
    (tmp_path / "report.json").write_text("new report")
    assert source_fingerprint(tmp_path) == first
    source.write_text("second")
    assert source_fingerprint(tmp_path) != first


def test_resume_rejects_different_content_and_preserves_old_provenance(tmp_path):
    from app.agents.registry import require_agent
    from app.llm.provider import resolve_model
    from quality_check import build_cases, resume_rows, settings_fingerprint

    args = SimpleNamespace(
        agents=["study"],
        model=None,
        no_judge=False,
        judge_model="test-judge",
        samples=1,
        allow_code_change=False,
    )
    args.generated_with = settings_fingerprint(args)
    old = {**args.generated_with, "source_sha256": "old-source"}
    slug, case = build_cases(["study"])[0]
    row = {
        "agent": slug,
        "case": case["id"],
        "sample": 1,
        "input": case["input"],
        "prompt_version": require_agent(slug).prompt_version,
        "model": resolve_model(require_agent(slug).model.model),
    }
    path = tmp_path / "partial.json"
    path.write_text(
        json.dumps(
            {
                "provider": settings.llm_provider,
                "judge_version": 3,
                "model": settings.llm_model,
                "judge_model": args.judge_model,
                "samples": 1,
                "generated_with": old,
                "results": [row],
            }
        )
    )
    with pytest.raises(ValueError, match="Saved rows"):
        resume_rows(path, args, [(slug, case, 1)])
    args.allow_code_change = True
    resumed = resume_rows(path, args, [(slug, case, 1)])
    assert resumed[0]["generated_with"] == old
    assert resumed[0]["generated_with"] != args.generated_with
