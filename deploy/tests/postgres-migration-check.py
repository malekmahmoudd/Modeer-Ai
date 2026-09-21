"""Run only in the disposable rehearsal database named below, never real data."""
import json
import subprocess

from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.models import User
from app.db.session import SessionLocal, engine

assert engine.url.database == "modeer_migration_20260914", "Requires isolated scratch database"
assert settings.llm_provider == "mock", "No live provider in migration checks"


def migrate(*args):
    subprocess.run(["alembic", *args], check=True)


migrate("upgrade", "head")
with SessionLocal() as session:
    user = User(display_name="Migration sentinel", session_epoch=3)
    session.add(user)
    session.commit()
    user_id = user.id
assert "recovery_codes" in inspect(engine).get_table_names()
migrate("downgrade", "0003")
assert "recovery_codes" not in inspect(engine).get_table_names()
migrate("upgrade", "head")
with SessionLocal() as session:
    user = session.get(User, user_id)
    assert user.display_name == "Migration sentinel" and user.session_epoch == 3
    assert user.password_hash is None
with engine.connect() as connection:
    revision = connection.execute(text("select version_num from alembic_version")).scalar_one()
assert revision == "0004"
print(json.dumps({"database": "PostgreSQL 16, disposable scratch database", "revision": revision,
                  "checks": ["empty database to head", "0004 to 0003 to head",
                             "user and session epoch preserved", "recovery table restored"],
                  "limitation": "Downgrade discards password/recovery data by design; use a backup for rollback."}))
