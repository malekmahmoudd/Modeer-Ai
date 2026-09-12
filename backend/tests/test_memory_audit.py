"""The audit flags what the old rules let through, and changes nothing."""

from __future__ import annotations

import sys

from sqlalchemy import func, select

from app.db.models import AgentMemory, SharedMemory
from tools import memory_audit


def _seed(db, user_id):
    db.add_all(
        [
            # Stored under the old rules: sensitive, but the model said it was not.
            SharedMemory(
                user_id=user_id,
                scope="shared",
                category="context",
                key="condition",
                value="diagnosed with asthma",
                source="study",
                confidence=0.9,
                sensitive=False,
            ),
            # A category the prompt never offered.
            SharedMemory(
                user_id=user_id,
                scope="shared",
                category="astrology",
                key="sign",
                value="libra",
                source="modeer",
                confidence=0.9,
                sensitive=False,
            ),
            # Ordinary and fine.
            SharedMemory(
                user_id=user_id,
                scope="shared",
                category="education",
                key="field_of_study",
                value="law",
                source="modeer",
                confidence=0.9,
                sensitive=False,
            ),
            # Saved by hand, sensitive words and all: the user's choice, never flagged.
            AgentMemory(
                user_id=user_id,
                agent_id="fitness",
                scope="agent",
                category="health",
                key="injury",
                value="knee injury",
                source="user",
                confidence=1.0,
                sensitive=False,
            ),
        ]
    )
    db.commit()


def test_audit_flags_old_rule_leftovers_and_skips_explicit_saves(db, make_user, capsys):
    user = make_user("Alice")
    _seed(db, user.id)

    argv, sys.argv = sys.argv, ["memory_audit", "--list"]
    try:
        memory_audit.main()
    finally:
        sys.argv = argv
    out = capsys.readouterr().out

    assert "2 flagged" in out
    assert "looks sensitive but is not flagged" in out
    assert "unknown category 'astrology'" in out
    assert "field_of_study" not in out, "an ordinary fact was flagged"
    assert "injury" not in out, "an explicit save was second-guessed"
    assert "diagnosed with asthma" not in out, "values printed without --values"


def test_audit_writes_nothing(db, make_user):
    user = make_user("Alice")
    _seed(db, user.id)
    before = (
        db.scalar(select(func.count()).select_from(SharedMemory)),
        db.scalar(select(func.count()).select_from(AgentMemory)),
    )

    argv, sys.argv = sys.argv, ["memory_audit"]
    try:
        memory_audit.main()
    finally:
        sys.argv = argv

    db.expire_all()
    after = (
        db.scalar(select(func.count()).select_from(SharedMemory)),
        db.scalar(select(func.count()).select_from(AgentMemory)),
    )
    assert before == after
    flags = db.scalars(select(SharedMemory.sensitive)).all()
    assert flags.count(True) == 0, "the audit reclassified a row"
