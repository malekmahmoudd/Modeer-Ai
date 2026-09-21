"""Run inside the disposable Linux worker; never against a live deployment."""
import json
import os
from pathlib import Path
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

root = Path("/qa")
env = {**os.environ, "MODEER_COMPOSE_FILE": "/qa/compose.yml", "MODEER_BACKUP_DIR": "/qa/backups", "MODEER_BACKUP_PASSPHRASE_FILE": "/qa/key", "MODEER_BACKUP_OFFHOST": "/qa/offhost"}
checks = []
def run(script, overrides=None, ok=True):
    result = subprocess.run(["sh", "/scripts/" + script], env={**env, **(overrides or {})}, capture_output=True, text=True)
    assert (result.returncode == 0) == ok, result.stdout + result.stderr
    return result

def passed(name):
    checks.append(name)
    print("PASS", name, flush=True)

run("backup.sh", {"MODEER_BACKUP_PASSPHRASE_FILE": "/qa/missing-key"}, ok=False)
run("backup.sh", {"MODEER_BACKUP_OFFHOST": ""}, ok=False)
passed("backup refuses missing encryption key or destination")
assert not list((root / "backups").glob("*.dump"))
assert not list((root / "backups").glob("*.partial"))
assert not (root / "backups/modeer-expired.dump.enc").exists()
assert not (root / "offhost/modeer-expired.dump.enc").exists()
assert (root / "offhost/unrelated.txt").exists()
passed("plaintext cleaned; both destinations expire archives and preserve unrelated files")
(root / "wrong-key").write_text("wrong-test-only")
run("restore-check.sh", {"MODEER_BACKUP_PASSPHRASE_FILE": "/qa/wrong-key"}, ok=False)
run("restore-check.sh", {"MODEER_BACKUP_DIR": "/qa/offhost"})
passed("wrong key rejected; copied archive restores successfully")

state = {"status": "ok", "accept": True, "alerts": []}
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        assert self.path == "/api/health/detail"
        self.send_response(200 if state["status"] == "ok" else 503)
        self.end_headers()
        self.wfile.write(json.dumps({"status": state["status"]}).encode())
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        state["alerts"].append(body)
        self.send_response(204 if state["accept"] else 500)
        self.end_headers()
server = HTTPServer(("127.0.0.1", 8099), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
watch = {"MODEER_URL": "http://127.0.0.1:8099", "ALERT_WEBHOOK_URL": "http://127.0.0.1:8099/alerts", "MODEER_WATCHDOG_STATE": "/qa/test-watchdog-state", "MODEER_WATCHDOG_TIMEOUT": "1"}
Path(watch["MODEER_WATCHDOG_STATE"]).unlink(missing_ok=True)
run("watchdog.sh", watch)
assert not state["alerts"]
state["status"] = "degraded"
run("watchdog.sh", watch, ok=False)
run("watchdog.sh", watch, ok=False)
assert len(state["alerts"]) == 1
passed("503 readiness triggers one alert per state change")
state["status"] = "ok"
state["accept"] = False
run("watchdog.sh", watch, ok=False)
assert Path(watch["MODEER_WATCHDOG_STATE"]).read_text() == "degraded"
state["accept"] = True
run("watchdog.sh", watch)
assert len(state["alerts"]) == 3
assert "RECOVERED" in state["alerts"][-1]["text"]
passed("failed alert delivery retries; successful recovery updates state")
before = len(state["alerts"])
run("nightly-backup.sh", {**watch, "MODEER_BACKUP_PASSPHRASE_FILE": "/qa/missing-key"}, ok=False)
assert len(state["alerts"]) == before + 1
assert "backup or restore failed" in state["alerts"][-1]["text"]
passed("nightly job reports backup failure to a local test webhook")
run("nightly-backup.sh", watch)
passed("nightly job backs up and immediately restores the copied archive")
# Compare every table in the restored schema, including password hashes,
# recovery-code consumption, session epochs and consent. Report equality only,
# never credential material. Other test writers must be stopped during this check.
compose = ["docker", "compose", "-f", "/qa/compose.yml", "exec", "-T", "db"]
def db_command(*args):
    return subprocess.run([*compose, *args], check=True, capture_output=True, text=True).stdout.strip()

def snapshot(database):
    tables = db_command("psql", "-U", "modeer", "-d", database, "-tAc",
                        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    return {table: db_command("psql", "-U", "modeer", "-d", database, "-tAc",
            f'SELECT count(*) || \':\' || md5(coalesce(string_agg(row_to_json(t)::text, \'\' ORDER BY row_to_json(t)::text), \'\')) FROM "{table}" t')
            for table in tables}

scratch = "modeer_ops_" + uuid.uuid4().hex
archive = max((root / "offhost").glob("modeer-*.dump.enc"), key=lambda p: p.stat().st_mtime)
plain = root / "verification.dump"
container_dump = "/tmp/" + scratch + ".dump"
container = subprocess.run(["docker", "compose", "-f", "/qa/compose.yml", "ps", "-q", "db"],
                           capture_output=True, text=True, check=True).stdout.strip()
try:
    subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "240000",
                    "-pass", "file:/qa/key", "-in", str(archive), "-out", str(plain)], check=True)
    subprocess.run(["docker", "cp", str(plain), container + ":" + container_dump], check=True)
    db_command("createdb", "-U", "modeer", scratch)
    db_command("pg_restore", "-U", "modeer", "-d", scratch, "--exit-on-error", "--no-owner", container_dump)
    assert snapshot("modeer") == snapshot(scratch)
    assert db_command("psql", "-U", "modeer", "-d", scratch, "-tAc",
                      "SELECT version_num FROM alembic_version") == "0004"
    passed("schema 0004 restore matches every source table, including credentials and consent")
    db_command("psql", "-U", "modeer", "-d", scratch, "-c",
               "UPDATE users SET display_name='populated restore sentinel'")
    assert snapshot("modeer") != snapshot(scratch)
    db_command("pg_restore", "-U", "modeer", "-d", scratch, "--clean", "--if-exists",
               "--exit-on-error", "--no-owner", container_dump)
    assert snapshot("modeer") == snapshot(scratch)
    passed("clean restore over populated scratch database recovers exact source rows")
finally:
    db_command("dropdb", "-U", "modeer", "--if-exists", scratch)
    db_command("rm", "-f", container_dump)
    plain.unlink(missing_ok=True)
server.shutdown()
run("watchdog.sh", {**watch, "MODEER_URL": "http://127.0.0.1:8098"}, ok=False)
passed("unreachable application produces a failing check")
(root / "linux-results.json").write_text(json.dumps({"environment": "disposable Docker Linux worker and PostgreSQL 16", "offhost_note": "Second directory on this machine, not physical off-host storage", "checks": checks}, indent=2))
