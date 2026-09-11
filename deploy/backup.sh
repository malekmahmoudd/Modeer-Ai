#!/usr/bin/env sh
# Linux host backup. Requires Docker Compose, openssl, flock and standard coreutils.
# Encryption and an existing off-host destination are mandatory; fail before dumping.
set -eu
umask 077
DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="${MODEER_COMPOSE_FILE:-$DIR/compose.yml}"
BACKUP_DIR="${MODEER_BACKUP_DIR:-$DIR/backups}"
KEEP_DAYS="${MODEER_BACKUP_KEEP_DAYS:-30}"
PASSPHRASE_FILE="${MODEER_BACKUP_PASSPHRASE_FILE:-}"
OFFHOST="${MODEER_BACKUP_OFFHOST:-}"
fail() { echo "$1" >&2; exit 1; }
case "$KEEP_DAYS" in ''|*[!0-9]*) fail "Retention must be a positive number of days" ;; esac
[ "$KEEP_DAYS" -gt 0 ] || fail "Retention must be positive"
[ -n "$PASSPHRASE_FILE" ] && [ -s "$PASSPHRASE_FILE" ] || fail "Missing or empty encryption key file"
[ -n "$OFFHOST" ] && [ -d "$OFFHOST" ] && [ -w "$OFFHOST" ] || fail "Off-host destination must already exist and be writable"
command -v openssl >/dev/null || fail "Install openssl on the backup host"
command -v flock >/dev/null || fail "Install flock on the backup host"
mkdir -p "$BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd -P)"
OFFHOST="$(cd "$OFFHOST" && pwd -P)"
[ "$BACKUP_DIR" != "$OFFHOST" ] || fail "Off-host destination must differ from local backup directory"
# Prevent overlap; kernel releases the lock even after a crash.
exec 9>"$BACKUP_DIR/.backup.lock"
flock -n 9 || fail "Another backup is already running"
compose() { docker compose --project-directory "$(dirname "$COMPOSE_FILE")" -f "$COMPOSE_FILE" "$@"; }
NAME="modeer-$(date -u +%Y%m%d-%H%M%S)-$$.dump"
DEST="$BACKUP_DIR/$NAME"
REMOTE_TMP="$OFFHOST/$NAME.enc.partial"
CONTAINER_ARCHIVE="/tmp/$NAME"
cleanup() {
  rm -f "$DEST" "$DEST.enc.partial" "$REMOTE_TMP"
  compose exec -T db rm -f "$CONTAINER_ARCHIVE" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
compose exec -T db pg_dump -U modeer -Fc -f "$CONTAINER_ARCHIVE" modeer
CONTAINER="$(compose ps -q db)"
[ -n "$CONTAINER" ] || fail "Database container is not running"
compose exec -T db pg_restore --list "$CONTAINER_ARCHIVE" >/dev/null
docker cp "$CONTAINER:$CONTAINER_ARCHIVE" "$DEST"
openssl enc -aes-256-cbc -pbkdf2 -iter 240000 -salt -pass "file:$PASSPHRASE_FILE" -in "$DEST" -out "$DEST.enc.partial"
mv "$DEST.enc.partial" "$DEST.enc"
cp "$DEST.enc" "$REMOTE_TMP"
cmp "$DEST.enc" "$REMOTE_TMP" || fail "Off-host copy differs"
mv "$REMOTE_TMP" "$OFFHOST/$NAME.enc"
# Preserve archive timestamps on both destinations; retention is not restarted by copying.
touch -r "$DEST.enc" "$OFFHOST/$NAME.enc"
MINUTES=$((KEEP_DAYS * 1440))
for directory in "$BACKUP_DIR" "$OFFHOST"; do
  find "$directory" -maxdepth 1 -type f -name 'modeer-*.dump*' -mmin "+$MINUTES" -print -delete
done
echo "BACKUP PASSED: encrypted, verified copy at $OFFHOST/$NAME.enc"
