"""Create an invite-only user. Writes credentials to a new local file, never logs them."""

import argparse
import hashlib
import json
import secrets
from pathlib import Path

from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal

parser = argparse.ArgumentParser()
parser.add_argument("--email", required=True)
parser.add_argument("--name", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
output = Path(args.output)
# Refuse overwriting credentials and create before committing the new user.
with output.open("x", encoding="utf8") as f, SessionLocal() as db:
    if db.scalar(select(User).where(User.email == args.email)):
        raise SystemExit("Account already exists; rotate its configured hash explicitly.")
    user = User(email=args.email, display_name=args.name)
    db.add(user)
    db.flush()
    key = secrets.token_urlsafe(32)
    json.dump(
        {
            "user_id": user.id,
            "access_key": key,
            "AUTH_ACCESS_KEYS_entry": {user.id: hashlib.sha256(key.encode()).hexdigest()},
        },
        f,
        indent=2,
    )
    f.flush()
    db.commit()
print("Account created. Credentials saved to the requested file; share the access key privately.")
