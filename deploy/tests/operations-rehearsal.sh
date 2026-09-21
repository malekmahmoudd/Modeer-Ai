#!/bin/sh
# Disposable docker:cli worker only. /qa is a NEW scratch directory and /source
# is a read-only mount of deploy/. Never use a production compose project here.
set -eu
timeout 120 apk add --no-cache python3 openssl util-linux coreutils curl
mkdir -p /scripts /qa/backups /qa/offhost
cp /source/*.sh /source/notify-operator.py /scripts/
sed -i 's/\r$//' /scripts/*
chmod +x /scripts/*.sh
cat > /qa/compose.yml <<'YAML'
name: modeer-rehearsal-20260914
services:
  db:
    image: postgres:16-alpine
YAML
printf '%s\n' 'disposable-rehearsal-only' > /qa/key
chmod 600 /qa/key
touch /qa/offhost/unrelated.txt
touch -d '40 days ago' /qa/backups/modeer-expired.dump.enc /qa/offhost/modeer-expired.dump.enc
export MODEER_COMPOSE_FILE=/qa/compose.yml MODEER_BACKUP_DIR=/qa/backups
export MODEER_BACKUP_PASSPHRASE_FILE=/qa/key MODEER_BACKUP_OFFHOST=/qa/offhost
sh /scripts/backup.sh
python3 /source/tests/linux-rehearsal.py
