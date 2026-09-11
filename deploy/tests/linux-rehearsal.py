"""Run inside the disposable Linux worker; never against a live deployment."""
import json
import os
from pathlib import Path
import subprocess
import threading
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
server.shutdown()
run("watchdog.sh", {**watch, "MODEER_URL": "http://127.0.0.1:8098"}, ok=False)
passed("unreachable application produces a failing check")
(root / "linux-results.json").write_text(json.dumps({"environment": "disposable Docker Linux worker and PostgreSQL 16", "offhost_note": "Second directory on this machine, not physical off-host storage", "checks": checks}, indent=2))
