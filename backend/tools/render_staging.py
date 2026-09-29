"""Start an isolated Render staging service; never use with production data.

Render generates STAGING_ACCESS_KEY. It is the staging invitation credential,
visible only in the service's environment settings; it is never printed here.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from urllib.parse import urlsplit

STAGING_USER = "d4083b06-07b8-48b6-88b0-84cfad299ada"


def prepare_environment(environ):
    if environ.get("FAREEQ_STAGING") != "true":
        raise ValueError("This launcher is only for isolated staging")
    url = urlsplit(environ["DATABASE_URL"])
    if url.scheme not in ("postgres", "postgresql", "postgresql+psycopg"):
        raise ValueError("Staging requires PostgreSQL")
    if url.path != "/fareeq_staging":
        raise ValueError("Refusing a database not named fareeq_staging")
    key = environ.get("STAGING_ACCESS_KEY", "")
    if len(key) < 32:
        raise ValueError("A strong staging invitation key is required")
    environ["DATABASE_URL"] = "postgresql+psycopg://" + environ["DATABASE_URL"].split("://", 1)[1]
    environ["AUTH_ACCESS_KEYS"] = json.dumps(
        {STAGING_USER: hashlib.sha256(key.encode()).hexdigest()}
    )
    environ["SIGNUP_ENABLED"] = "false"


def main():
    prepare_environment(os.environ)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    from app.db.models import User
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        if db.get(User, STAGING_USER) is None:
            db.add(
                User(id=STAGING_USER, display_name="Staging tester", email="staging@fareeq.test")
            )
            db.commit()
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            os.environ.get("PORT", "8000"),
            "--no-access-log",
        ],
    )


if __name__ == "__main__":
    main()
