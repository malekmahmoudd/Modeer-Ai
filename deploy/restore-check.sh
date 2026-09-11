#!/usr/bin/env sh
# Restore the newest backup into a throwaway database and prove it holds rows.
#
# An unrestored backup is a guess. This turns it into a fact, without touching
# the live database: it restores into a uniquely named scratch database and
# drops it again.
#
#   MODEER_BACKUP_PASSPHRASE_FILE=/etc/modeer/backup.key ./restore-check.sh
#
# Run it from cron straight after backup.sh. A backup job that never verifies
# is how people discover at recovery time that they have been archiving
# nothing for six months.
#
# Decryption uses host openssl; Docker is used only for the database.
set -eu
umask 077

DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="${MODEER_COMPOSE_FILE:-$DIR/compose.yml}"
BACKUP_DIR="${MODEER_BACKUP_DIR:-$DIR/backups}"
PASSPHRASE_FILE="${MODEER_BACKUP_PASSPHRASE_FILE:-}"
ARCHIVE="${1:-}"

compose() {
  docker compose --project-directory "$(dirname "$COMPOSE_FILE")" -f "$COMPOSE_FILE" "$@"
}

if [ -z "$ARCHIVE" ]; then
  ARCHIVE="$(ls -1t "$BACKUP_DIR"/modeer-*.dump.enc 2>/dev/null | head -n 1 || true)"
fi
[ -n "$ARCHIVE" ] && [ -f "$ARCHIVE" ] || { echo "no archive found in $BACKUP_DIR" >&2; exit 1; }
echo "Checking: $ARCHIVE"

SCRATCH="modeer_restore_$(date -u +%s)_$$"
CONTAINER_ARCHIVE="/tmp/$SCRATCH.dump"
CONTAINER="$(compose ps -q db)"
[ -n "$CONTAINER" ] || { echo "database container is not running" >&2; exit 1; }

PLAIN="$ARCHIVE"
TEMPORARY=""
cleanup() {
  compose exec -T db psql -U modeer -d postgres -c "DROP DATABASE IF EXISTS $SCRATCH" >/dev/null 2>&1 || true
  compose exec -T db rm -f "$CONTAINER_ARCHIVE" >/dev/null 2>&1 || true
  [ -n "$TEMPORARY" ] && rm -f "$TEMPORARY"
  return 0
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

case "$ARCHIVE" in
  *.enc)
    [ -n "$PASSPHRASE_FILE" ] && [ -f "$PASSPHRASE_FILE" ] || {
      echo "encrypted archive needs MODEER_BACKUP_PASSPHRASE_FILE" >&2; exit 1; }
    TEMPORARY="$(mktemp)"
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 240000 \
      -pass "file:$PASSPHRASE_FILE" -in "$ARCHIVE" -out "$TEMPORARY"
    PLAIN="$TEMPORARY"
    ;;
esac

docker cp "$PLAIN" "$CONTAINER:$CONTAINER_ARCHIVE"
compose exec -T db psql -U modeer -d postgres -c "CREATE DATABASE $SCRATCH" >/dev/null
compose exec -T db pg_restore -U modeer -d "$SCRATCH" --exit-on-error --no-owner "$CONTAINER_ARCHIVE"

COUNTS="$(compose exec -T db psql -U modeer -d "$SCRATCH" -tAc "
SELECT 'users=' || (SELECT count(*) FROM users)
    || ' memories=' || (SELECT count(*) FROM shared_memories)
    || ' messages=' || (SELECT count(*) FROM messages)")"
echo "Restored rows: $COUNTS"

case "$COUNTS" in
  *users=0*) echo "restored database has no users - archive is not usable" >&2; exit 1 ;;
esac

echo "RESTORE CHECK PASSED"
