"""Create an invite-only account, or rotate the key of one that exists.

Credentials are written to a new local file and never logged. Both modes print
only what is safe to see on a terminal that may be shared or recorded.

    python provision_user.py --email a@b.test --name Alex --output invite.json
    python provision_user.py --rotate --email a@b.test --output new-key.json

Rotation is the recovery path for a lost or leaked access key. It mints a new
key for one account and bumps that account's session generation, so every
device holding the old cookie is signed out. Nobody else is affected — unlike
rotating AUTH_SECRET, which signs out every account at once.

After either command, merge the printed AUTH_ACCESS_KEYS_entry into
AUTH_ACCESS_KEYS in deploy/.env and restart the backend. For a rotation, REMOVE
the account's old entry: leaving it in place keeps the lost key working, which
is the whole thing you are trying to undo.
"""

import argparse
import hashlib
import json
import secrets
from pathlib import Path

from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal


def _credentials(user: User) -> tuple[str, dict]:
    key = secrets.token_urlsafe(32)
    return key, {
        "user_id": user.id,
        "access_key": key,
        "AUTH_ACCESS_KEYS_entry": {user.id: hashlib.sha256(key.encode()).hexdigest()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", help="Display name. Required when creating an account.")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Issue a new key for an existing account and end its live sessions",
    )
    args = parser.parse_args()

    if not args.rotate and not args.name:
        parser.error("--name is required when creating an account")

    output = Path(args.output)
    # Open with "x" so an existing credentials file is never overwritten, and do
    # it before touching the database so a refusal leaves no half-made account.
    with output.open("x", encoding="utf8") as handle, SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == args.email))

        if args.rotate:
            if existing is None:
                raise SystemExit(f"No account with email {args.email}")
            existing.session_epoch = (existing.session_epoch or 0) + 1
            key, payload = _credentials(existing)
            payload["rotated"] = True
            payload["sessions_revoked"] = True
            message = (
                "Key rotated and every existing session for this account ended.\n"
                "Replace this account's old entry in AUTH_ACCESS_KEYS — do not just add "
                "the new one, or the lost key keeps working — then restart the backend."
            )
        else:
            if existing is not None:
                raise SystemExit("Account already exists; use --rotate to issue a new key.")
            user = User(email=args.email, display_name=args.name)
            db.add(user)
            db.flush()
            key, payload = _credentials(user)
            message = (
                "Account created. Merge AUTH_ACCESS_KEYS_entry into AUTH_ACCESS_KEYS, "
                "restart the backend, and share the access key privately."
            )

        json.dump(payload, handle, indent=2)
        handle.flush()
        db.commit()

    print(f"{message}\nCredentials written to {output}. Delete it after secure delivery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
