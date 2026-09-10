# Private deployment runbook

This prepares an invite-only deployment, not public signup. No hosting account or domain has been selected and nothing has been published.

## Configuration

Copy deploy/.env.example to deploy/.env. Generate a URL-safe random hex database password, a separate random AUTH_SECRET of at least 32 characters, and set DOMAIN and the provider key. Never commit this file. The production backend refuses to start with demo authentication, debugging, an HTTP frontend origin, a missing signing secret, or malformed access-key hashes.

Only Caddy publishes ports 80 and 443. PostgreSQL and the backend remain on the private Compose network. Caddy supplies HTTPS and disables proxy buffering for streamed replies. DNS for DOMAIN must point to your host; outbound HTTPS access to the provider is required.

## Bootstrap accounts

**The ordering below is not optional.** Production fails closed: with
`AUTH_REQUIRED=true` and no `AUTH_ACCESS_KEYS`, the backend refuses to start. But
you cannot mint an access key without a database, and the database is only
reachable once the stack is up. The way through is to bring up **only** the
database, then run the migration and provisioning steps in one-off containers
that opt out of production mode. That override is safe here and nowhere else:

- it applies to a single `docker compose run` container, never to the long-lived
  backend service;
- that container publishes no port and is removed immediately after;
- it is used only for `alembic upgrade head` and `provision_user.py`, neither of
  which serves traffic.

Never set `AUTH_REQUIRED=false` on the `backend` **service**, and never leave a
provisioning container running. If a step fails, `docker compose down` and start
the sequence again rather than relaxing the service configuration.

Run these commands from the repository root after setting the environment file:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yml up -d db
docker compose --env-file deploy/.env -f deploy/compose.yml run --rm -e ENVIRONMENT=development -e AUTH_REQUIRED=false backend alembic upgrade head
docker compose --env-file deploy/.env -f deploy/compose.yml run --name modeer-provision -e ENVIRONMENT=development -e AUTH_REQUIRED=false backend python provision_user.py --email person@example.com --name Person --output /tmp/invite.json
docker cp modeer-provision:/tmp/invite.json ./invite.json
docker rm modeer-provision
```

The bootstrap override applies only to that one-off container; it publishes no port. Read invite.json locally. Merge its AUTH_ACCESS_KEYS_entry into the AUTH_ACCESS_KEYS JSON object in deploy/.env. Give the access_key privately to that person. Delete the local invite file after secure delivery. Repeat for each account. The app's /login page exchanges the key for a signed HttpOnly, SameSite=Strict cookie, Secure in production, expiring after seven days. Sessions are checked on the server; removing a hash revokes all that user's sessions. Change the signing secret to revoke all sessions. Access keys are high-entropy private invitations, not reusable human passwords.

```sh
docker compose --env-file deploy/.env -f deploy/compose.yml up -d --build
```

Confirm /api/health, login, logout, persistence across restart, and cross-account denial before inviting others. Keep the beta small: the provider's shared token quota is not multiplied by the number of users. For a public launch, add managed identity/recovery, distributed request quotas, production monitoring and a security review.

## Backup and restore

`deploy/backup.ps1` dumps the database in PostgreSQL custom format, verifies the
archive with `pg_restore --list`, encrypts it with AES-256, copies it off-host,
and prunes old copies. Backups contain every conversation and stored memory, so
treat them like the database itself.

```powershell
$env:MODEER_BACKUP_PASSPHRASE_FILE = 'C:\secure\modeer-backup.key'   # not in the repo
$env:MODEER_BACKUP_OFFHOST         = 'E:\offsite\modeer'             # or a mounted remote
./deploy/backup.ps1 -KeepDays 30
```

| Setting | Default | Notes |
|---|---|---|
| `-KeepDays` | 30 | Archives older than this are deleted. `0` disables pruning. |
| `-OffHost` / `MODEER_BACKUP_OFFHOST` | unset | A backup on the same disk as the database is not a backup. The script warns when unset. |
| `-PassphraseFile` / `MODEER_BACKUP_PASSPHRASE_FILE` | unset | Without it the archive is left unencrypted and the script warns. Store the passphrase somewhere the backup host cannot reach. |

Schedule it daily (Task Scheduler, running as a user with Docker access). Keep at
least seven daily copies; 30 is the default because the dumps are small.

**Verify restores, do not assume them.** `deploy/restore-check.ps1` restores the
newest archive into a scratch database, counts users, memories and messages,
then drops it. The live database is untouched, so run it monthly — or nightly
after the backup:

```powershell
./deploy/restore-check.ps1
```

It fails loudly if the archive will not restore or restores with no users. For a
real recovery, restore to a **new database**, never over the live one:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yml exec db createdb -U modeer modeer_restore
docker compose --env-file deploy/.env -f deploy/compose.yml ps -q db
# Use that container ID:
docker cp PATH_TO_BACKUP.dump CONTAINER_ID:/tmp/restore.dump
docker compose --env-file deploy/.env -f deploy/compose.yml exec db pg_restore -U modeer -d modeer_restore --no-owner /tmp/restore.dump
```

Point a separate test backend at modeer_restore, verify record counts, log in and inspect restored conversations. Switch the live database only during an explicitly planned recovery.

For local SQLite, backend/backup_sqlite.py uses SQLite's online backup API and integrity_check; it refuses overwriting. The isolated journey database was snapshotted and reopened with matching user/message/memory counts.

### Not yet verified

Docker's Linux engine will not start on this machine: **WSL is not installed**
(`wsl --status` reports it missing), and Docker Desktop is configured for the
`desktop-linux` context, so the daemon has no backend. Until someone runs
`wsl --install` from an elevated prompt and reboots, the following remain
unverified and must be checked before this is called deployable:

- image builds for backend and frontend;
- `alembic upgrade head` against PostgreSQL rather than SQLite;
- HTTPS issuance and streaming through Caddy;
- data persistence across `docker compose down` / `up`;
- `deploy/backup.ps1` and `deploy/restore-check.ps1` end to end — both are
  written against a running stack and have not been executed.

Compose syntax validation passed. Everything above is reviewed but untested.

## Updates and rollback

Take a backup first. Build the new images and record the source commit. Apply migrations before application startup (the backend container does this). Keep previous images until the new version passes smoke tests. Do not automatically downgrade a production database; rehearse schema rollback or restore on a copy.

The desktop app remains in local development mode until you explicitly configure production. Existing local data has not been converted into shared accounts.

