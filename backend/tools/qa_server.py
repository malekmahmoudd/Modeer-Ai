"""Run the API against a throwaway database with authentication switched on.

For manual browser QA of the real login flow: point the frontend at this port,
sign in with the printed access key, and click through onboarding, chat, memory
and history without touching the development database.

The signing secret and access key here are fixed and public. That is fine
because nothing real is behind them — never run this against a real database.

    python -m tools.qa_server                     # mock model, port 8002
    python -m tools.qa_server --live --port 8003  # real provider
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

QA_ACCESS_KEY = "q" * 40
QA_SECRET = "qa-signing-secret-not-for-production-0123456789"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--db", default="journey-qa.db")
    parser.add_argument("--live", action="store_true", help="use the configured provider")
    parser.add_argument("--frontend", default="http://localhost:3000")
    parser.add_argument("--reset", action="store_true", help="start from an empty database")
    args = parser.parse_args()

    db_path = Path(args.db)
    if args.reset and db_path.exists():
        db_path.unlink()

    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///./{db_path.name}"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["FRONTEND_URL"] = args.frontend
    if not args.live:
        os.environ["LLM_PROVIDER"] = "mock"
        os.environ["MEMORY_EXTRACTION"] = "rules"

    from app.agents.sync import sync_agents
    from app.db.base import Base
    from app.db.models import User
    from app.db.session import SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        sync_agents(db)
        user = db.query(User).first()
        if user is None:
            user = User(display_name="QA", email="qa@local.test")
            db.add(user)
        db.commit()
        user_id = user.id

    os.environ["AUTH_REQUIRED"] = "true"
    os.environ["AUTH_SECRET"] = QA_SECRET
    os.environ["AUTH_ACCESS_KEYS"] = json.dumps(
        {user_id: hashlib.sha256(QA_ACCESS_KEY.encode()).hexdigest()}
    )

    from app.core.config import settings

    settings.auth_required = True
    settings.auth_secret = QA_SECRET
    settings.auth_access_keys = {user_id: hashlib.sha256(QA_ACCESS_KEY.encode()).hexdigest()}
    settings.frontend_url = args.frontend

    print(f"QA API on http://127.0.0.1:{args.port}  db={db_path.name}")
    print(f"provider={'live: ' + settings.llm_provider if args.live else 'mock'}")
    print(f"frontend origin={args.frontend}")
    print(f"access key: {QA_ACCESS_KEY}\n")

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
