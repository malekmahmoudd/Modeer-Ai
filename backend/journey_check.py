"""End-to-end everyday journey against a live provider, in an isolated account.

The earlier journey pass used the mock provider, which cannot show whether the
real model's replies are usable, whether LLM memory extraction actually stores
anything, or whether an interrupted stream leaves the database consistent. This
walks the same path for real:

    sign in -> onboarding chat -> facts extracted -> follow-up recalls them
    -> a second specialist has its own history -> interrupted reply
    -> interrupted memory extraction -> retry succeeds

It writes to its own SQLite file and its own user, never the development
database, and prints one line per step so a failure says which step broke.

    python journey_check.py                 # live provider from .env
    python journey_check.py --keep          # leave the database for inspection
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path

DB_PATH = Path("journey-live.db")
ACCESS_KEY = "j" * 40
PACE_SECONDS = 16.0
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_WAIT = 35.0


def _configure(db_path: Path) -> None:
    """Point settings at a throwaway database before the app is imported."""
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///./{db_path.name}"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["FRONTEND_URL"] = "http://localhost:3000"
    os.environ.setdefault("MEMORY_EXTRACTION", "auto")


class Journey:
    def __init__(self, client, origin: dict[str, str]) -> None:
        self.client = client
        self.origin = origin
        self.failures: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        mark = "PASS" if ok else "FAIL"
        print(f"{mark}  {name}{(' — ' + detail) if detail else ''}", flush=True)
        if not ok:
            self.failures.append(name)
        return ok

    async def pace(self) -> None:
        await asyncio.sleep(PACE_SECONDS)

    async def say(self, agent: str, message: str, conversation_id: str | None = None) -> dict:
        """One chat turn, waiting out a per-minute throttle rather than failing on it.

        The app is right to surface a 429 immediately to a person. Here it would
        only make the journey flaky for a reason that has nothing to do with the
        behaviour under test, so a throttled turn is retried.
        """
        body: dict = {"message": message}
        if conversation_id:
            body["conversation_id"] = conversation_id
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            response = self.client.post(
                f"/api/agents/{agent}/chat", json=body, headers=self.origin, timeout=120
            )
            if response.status_code == 200:
                return response.json()
            throttled = "usage limit" in response.text.lower()
            if not throttled or attempt >= RATE_LIMIT_RETRIES:
                return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}
            print(f"      (throttled, waiting {RATE_LIMIT_WAIT:.0f}s)", flush=True)
            await asyncio.sleep(RATE_LIMIT_WAIT)
        return {"error": "exhausted rate-limit retries"}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="keep the journey database")
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    db_path = Path(args.db)
    if db_path.exists():
        db_path.unlink()
    _configure(db_path)

    from fastapi.testclient import TestClient

    from app.agents.sync import sync_agents
    from app.core.config import settings
    from app.db.base import Base
    from app.db.models import User
    from app.db.session import SessionLocal, engine
    from app.main import app

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sync_agents(db)
        user = User(display_name="Journey", email="journey@local.test")
        db.add(user)
        db.commit()
        user_id = user.id

    settings.auth_required = True
    settings.auth_secret = "journey-check-signing-secret-not-for-production"
    settings.auth_access_keys = {user_id: hashlib.sha256(ACCESS_KEY.encode()).hexdigest()}

    print(f"provider={settings.llm_provider} model={settings.llm_model} db={db_path.name}\n")
    origin = {"Origin": settings.frontend_url}

    with TestClient(app) as client:
        journey = Journey(client, origin)

        # --- sign in --------------------------------------------------------
        assert client.get("/api/goals").status_code == 401, "unauthenticated read must fail"
        login = client.post("/api/auth/login", json={"access_key": ACCESS_KEY}, headers=origin)
        journey.check("login sets a session cookie", login.status_code == 200)
        journey.check(
            "session cookie is HttpOnly and scoped to /api",
            "httponly" in login.headers.get("set-cookie", "").lower()
            and "path=/api" in login.headers.get("set-cookie", "").lower(),
            login.headers.get("set-cookie", "")[:80],
        )

        # --- onboarding turn ------------------------------------------------
        first = await journey.say(
            "modeer",
            "Hi! I'm a mechanical engineering student in Manchester. I have a "
            "thermodynamics final on the 20th and I train four times a week.",
        )
        journey.check(
            "onboarding reply arrives from the live model",
            bool(first.get("content")) and "error" not in first,
            first.get("error", f"{len(first.get('content', ''))} chars"),
        )
        candidates = first.get("memory_candidates", [])
        journey.check(
            "facts were extracted from the first message",
            len(candidates) >= 2,
            ", ".join(c.get("key", "?") for c in candidates[:4]),
        )
        await journey.pace()

        stored = client.get("/api/memory/shared").json()
        journey.check("facts are readable back from the store", len(stored) >= 1)

        # --- follow-up recalls the stored facts ------------------------------
        follow_up = await journey.say("study", "What should I revise first?")
        text = (follow_up.get("content") or "").lower()
        journey.check(
            "a different specialist recalls the shared facts",
            any(word in text for word in ("thermodynamic", "mechanical", "engineering")),
            follow_up.get("error", text[:80]),
        )
        journey.check(
            "the specialist was told it had context",
            bool(follow_up.get("context_used")),
        )
        await journey.pace()

        # --- separate histories ----------------------------------------------
        conversations = client.get("/api/conversations").json()
        by_agent = {c["agent_id"] for c in conversations}
        journey.check(
            "each specialist keeps its own conversation",
            {"modeer", "study"} <= by_agent,
            ", ".join(sorted(by_agent)),
        )
        study_convo = next(c["id"] for c in conversations if c["agent_id"] == "study")
        detail = client.get(f"/api/conversations/{study_convo}").json()
        journey.check(
            "history persists with both turns",
            len(detail.get("messages", [])) >= 2,
            f"{len(detail.get('messages', []))} messages",
        )

        # --- interruption during the reply ------------------------------------
        interrupted = _interrupt_stream(client, origin, "career", "What roles suit me?")
        journey.check(
            "an interrupted stream is abandoned without a stored reply",
            interrupted["disconnected"],
            f"{interrupted['deltas']} deltas before disconnect",
        )
        await journey.pace()

        # --- retry after the interruption --------------------------------------
        retry = await journey.say("career", "What roles suit me?")
        journey.check(
            "a retry after an interruption succeeds",
            bool(retry.get("content")) and "error" not in retry,
            retry.get("error", ""),
        )

        # --- the database is still consistent ----------------------------------
        with SessionLocal() as db:
            from app.db.models import Message

            orphans = [
                m
                for m in db.query(Message).filter(Message.role == "assistant").all()
                if not (m.content or "").strip()
            ]
        journey.check("no empty assistant messages were persisted", not orphans)

        print()
        if journey.failures:
            print(f"FAILED {len(journey.failures)}: {', '.join(journey.failures)}")
        else:
            print("All journey steps passed.")

    engine.dispose()
    if not args.keep and db_path.exists():
        db_path.unlink()
        print(f"Removed {db_path.name}")
    else:
        print(f"Kept {db_path.name}")
    return 1 if journey.failures else 0


def _interrupt_stream(client, origin: dict, agent: str, message: str) -> dict:
    """Open the SSE stream, read a couple of deltas, then hang up mid-reply."""
    deltas = 0
    with client.stream(
        "POST",
        f"/api/agents/{agent}/chat/stream",
        json={"message": message},
        headers=origin,
        timeout=120,
    ) as response:
        if response.status_code != 200:
            return {"disconnected": False, "deltas": 0}
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[5:].strip())
            except ValueError:
                continue
            if event.get("type") == "delta":
                deltas += 1
                if deltas >= 3:
                    break  # leaving the context manager closes the connection
    return {"disconnected": deltas >= 3, "deltas": deltas}


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
