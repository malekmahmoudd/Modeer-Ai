"""Create the two rehearsal accounts named in compose.yml. Safe to run twice.

docker compose exec -T -e PYTHONPATH=/app backend python /rehearsal/seed_users.py
"""

from app.db.models import User
from app.db.session import SessionLocal

ACCOUNTS = {
    "00000000-0000-4000-8000-00000000000a": ("Rehearsal A", "a@rehearsal.test"),
    "00000000-0000-4000-8000-00000000000b": ("Rehearsal B", "b@rehearsal.test"),
}

with SessionLocal() as db:
    for account, (name, email) in ACCOUNTS.items():
        if db.get(User, account) is None:
            db.add(User(id=account, display_name=name, email=email))
    db.commit()
print(f"{len(ACCOUNTS)} rehearsal accounts ready")
