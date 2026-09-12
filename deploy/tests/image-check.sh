#!/bin/sh
# Inside the built backend image: prove it holds exactly requirements.lock, then
# run the backend suite on that set. See docs/DEPLOYMENT.md, "Backend dependency lock".
#
#   docker build -t modeer-backend:check backend
#   docker run --rm -v "$PWD/backend/tests:/app/tests:ro" \
#     -v "$PWD/deploy/tests/image-check.sh:/image-check.sh:ro" modeer-backend:check sh /image-check.sh
set -eu
python - <<'PY'
import re, subprocess, sys
lock = {}
for line in open("/app/requirements.lock"):
    m = re.match(r"^([A-Za-z0-9_.-]+)==([^ \\]+)", line)
    if m:
        lock[m.group(1).lower().replace("_", "-")] = m.group(2)
frozen = {}
out = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"], capture_output=True, text=True, check=True)
for line in out.stdout.splitlines():
    name, _, version = line.partition("==")
    frozen[name.lower().replace("_", "-")] = version
extra = sorted(set(frozen) - set(lock) - {"pip"})
missing = sorted(set(lock) - set(frozen))
wrong = sorted(n for n in lock if n in frozen and frozen[n] != lock[n])
print(f"lock={len(lock)} installed={len(frozen)} extra={extra} missing={missing} wrong={wrong}")
sys.exit(1 if extra or missing or wrong else 0)
PY
# Test tools go to a separate prefix so the image's own set stays untouched.
pip install --quiet --no-cache-dir --target /tmp/testtools pytest==8.4.2 pytest-asyncio==0.24.0
cd /app
PYTHONPATH=/tmp/testtools PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests
