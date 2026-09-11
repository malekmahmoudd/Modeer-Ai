#!/usr/bin/env sh
# Source the private operations env in the scheduler before invoking this job.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
if "$DIR/backup.sh" && MODEER_BACKUP_DIR="$MODEER_BACKUP_OFFHOST" "$DIR/restore-check.sh"; then
  echo "NIGHTLY BACKUP AND RESTORE PASSED"
else
  echo "Nightly backup or restore failed; inspect the host job log" >&2
  python3 "$DIR/notify-operator.py" "Modeer nightly backup or restore failed. Inspect the host job log." || true
  exit 1
fi
