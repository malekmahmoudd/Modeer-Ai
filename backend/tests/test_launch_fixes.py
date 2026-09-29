"""Launch regressions: proxy policy, build privacy and reminder abuse limits."""

from pathlib import Path

from app.core.config import settings
from app.push import service

ROOT = Path(__file__).resolve().parents[2]


def test_proxy_allows_same_origin_microphone():
    for path in (ROOT / "deploy/Caddyfile", ROOT / "docs/DEPLOYMENT.md"):
        content = path.read_text()
        assert "microphone=(self)" in content
        assert "microphone=()" not in content
    assert "camera=()" in (ROOT / "deploy/Caddyfile").read_text()


def test_database_artifacts_excluded_from_image_context():
    # These patterns cover backup suffixes and SQLite journal/sidecar files.
    patterns = (ROOT / "backend/.dockerignore").read_text().splitlines()
    assert {"*.db*", "*.sqlite*", "*.bak*", "backups", ".env*"} <= set(patterns)
    assert {"**/*.db*", "**/*.sqlite*", "**/*.bak*", "**/backups", "**/.env*"} <= set(patterns)


def test_test_push_is_rate_limited_per_account(client, monkeypatch, make_user):
    alice, bob = make_user("Alice"), make_user("Bob")
    sent = []

    async def send(db, user, payload):
        sent.append(user.id)
        return 1

    monkeypatch.setattr(service, "send", send)
    monkeypatch.setattr(settings, "auth_required", False)
    # Freeze the quota window so the assertion cannot straddle a minute.
    monkeypatch.setattr("app.core.usage.time.time", lambda: 1800000000)
    for _ in range(3):
        assert client.post("/api/push/test", headers={"X-User-Id": alice.id}).status_code == 200
    denied = client.post("/api/push/test", headers={"X-User-Id": alice.id})
    assert denied.status_code == 429
    assert int(denied.headers["Retry-After"]) > 0
    assert sent == [alice.id] * 3
    assert client.post("/api/push/test", headers={"X-User-Id": bob.id}).status_code == 200
    assert sent[-1] == bob.id
