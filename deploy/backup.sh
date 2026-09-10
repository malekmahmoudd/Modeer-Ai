#!/usr/bin/env sh
# Back up the Modeer database on a Linux host: dump, verify, encrypt, prune,
# copy off-host.
#
# The PowerShell scripts beside this one are for a Windows workstation. The
# production host is Linux, so a backup that only runs on the developer's
# laptop is not a backup of production. This is the one cron actually runs.
#
#   MODEER_BACKUP_PASSPHRASE_FILE=/etc/modeer/backup.key \
#   MODEER_BACKUP_OFFHOST=/mnt/offsite/modeer \
#   ./backup.sh
#
# Exit codes: 0 success, non-zero means NO usable backup was produced. Cron
# mails the output on failure, so every failure path prints why.
#
# RUN THIS ON THE HOST, NOT INSIDE A CONTAINER. The encryption step mounts the
# backup directory into a helper container, and "docker run -v" paths are
# resolved by the HOST daemon. From inside a container the path is the
# container's, the host has no such directory, and openssl silently finds an
# empty mount. A cron entry on the host is the intended arrangement.
set -eu

DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="${MODEER_COMPOSE_FILE:-$DIR/compose.yml}"
BACKUP_DIR="${MODEER_BACKUP_DIR:-$DIR/backups}"
KEEP_DAYS="${MODEER_BACKUP_KEEP_DAYS:-30}"
PASSPHRASE_FILE="${MODEER_BACKUP_PASSPHRASE_FILE:-}"
OFFHOST="${MODEER_BACKUP_OFFHOST:-}"
OPENSSL_IMAGE="${MODEER_OPENSSL_IMAGE:-alpine/openssl:3.5.8}"

compose() {
  docker compose --project-directory "$DIR" -f "$COMPOSE_FILE" "$@"
}

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
NAME="modeer-$STAMP.dump"
DEST="$BACKUP_DIR/$NAME"

# Write the archive inside the container, then copy it out: piping pg_dump
# through the shell risks a mangled binary stream.
compose exec -T db pg_dump -U modeer -Fc -f /tmp/modeer-backup.dump modeer
CONTAINER="$(compose ps -q db)"
[ -n "$CONTAINER" ] || { echo "database container is not running" >&2; exit 1; }
docker cp "$CONTAINER:/tmp/modeer-backup.dump" "$DEST"

# Prove it is an archive, not merely a non-empty file.
compose exec -T db pg_restore --list /tmp/modeer-backup.dump >/dev/null
compose exec -T db rm -f /tmp/modeer-backup.dump

ARTIFACT="$DEST"

if [ -n "$PASSPHRASE_FILE" ] && [ -f "$PASSPHRASE_FILE" ]; then
  PASS_DIR="$(cd "$(dirname "$PASSPHRASE_FILE")" && pwd)"
  PASS_NAME="$(basename "$PASSPHRASE_FILE")"
  # The passphrase file is mounted and read by openssl itself, never piped:
  # a shell that appends a newline silently changes the passphrase and
  # produces archives only this script can open.
  docker run --rm \
    -v "$BACKUP_DIR:/backup" -v "$PASS_DIR:/pass:ro" "$OPENSSL_IMAGE" \
    enc -aes-256-cbc -pbkdf2 -iter 240000 -salt \
    -pass "file:/pass/$PASS_NAME" -in "/backup/$NAME" -out "/backup/$NAME.enc"
  rm -f "$DEST"
  ARTIFACT="$DEST.enc"
  echo "Encrypted: $ARTIFACT"
else
  echo "WARNING: backup is NOT encrypted (set MODEER_BACKUP_PASSPHRASE_FILE)." >&2
  echo "It contains every stored personal memory." >&2
fi

if [ -n "$OFFHOST" ]; then
  mkdir -p "$OFFHOST"
  cp "$ARTIFACT" "$OFFHOST/"
  echo "Copied off-host: $OFFHOST"
else
  echo "WARNING: no off-host copy (set MODEER_BACKUP_OFFHOST)." >&2
  echo "A backup on the same disk as the database is not a backup." >&2
fi

if [ "$KEEP_DAYS" -gt 0 ]; then
  find "$BACKUP_DIR" -name 'modeer-*.dump*' -type f -mtime "+$KEEP_DAYS" -print -delete
fi

echo "Backup saved: $ARTIFACT"
