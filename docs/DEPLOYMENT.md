# Private deployment runbook

This prepares an invite-only deployment, not public signup. No hosting account or domain has been selected and nothing has been published.

## Usage-limit migration

Before starting this version, run `alembic upgrade head` using the existing deployment migration procedure. Revision 0002 adds `usage_buckets`; the schema now has ten application tables. Configure `ACCOUNT_REQUESTS_PER_MINUTE` and `ACCOUNT_DAILY_TOKEN_BUDGET` for the size of the invite list; see [usage-limits.md](usage-limits.md). The prior container/backup verification was on revision 0001 (nine tables). The new migration has been rehearsed on SQLite and an isolated PostgreSQL 16 container, including downgrade/re-upgrade, concurrent quota admission, and persistence across separate processes.

**Rerun with revision 0002 (2026-09-10):** the container stack and the full
backup round-trip have now been verified on the ten-table schema. `usage_buckets`
is created by `alembic upgrade head` against PostgreSQL 16, and a populated-database
recovery rehearsal (`restore-check.ps1 -RehearseOverwrite`) passed with usage-ledger
rows present — every public table's contents matched the archive after restore and
the deliberately inserted sentinel row was gone. Note that `window` is a reserved
word in PostgreSQL: hand-written SQL against `usage_buckets` must quote it
(`"window"`). SQLAlchemy quotes it for you; a psql one-liner will not.

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

**Build before you migrate.** `docker compose run backend alembic upgrade head`
runs the migrations *inside the image*, not the ones in your working tree. A
stale image migrates to its own idea of head and reports success — this was
observed with revision 0002: `alembic heads` said `0001 (head)` from an image
built before 0002 existed, so `usage_buckets` was silently never created and
account limits would have failed in production against an apparently healthy
deployment. The `--build` in the first line below is not optional.

Run these commands from the repository root after setting the environment file:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yml build backend
docker compose --env-file deploy/.env -f deploy/compose.yml up -d db
docker compose --env-file deploy/.env -f deploy/compose.yml run --rm -e ENVIRONMENT=development -e AUTH_REQUIRED=false backend alembic upgrade head
# Confirm the schema is where you expect before going further:
docker compose --env-file deploy/.env -f deploy/compose.yml run --rm -e ENVIRONMENT=development -e AUTH_REQUIRED=false backend alembic current
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

It fails loudly if the archive will not restore or restores with no users.

**The archive is plain `openssl enc`, on purpose.** In a real recovery you may
not have these scripts, this repo, or Windows. Any machine with openssl and
`pg_restore` can get the data back:

```sh
openssl enc -d -aes-256-cbc -pbkdf2 -iter 240000 \
  -pass file:/path/to/passphrase -in modeer-TIMESTAMP.dump.enc -out modeer.dump
pg_restore --list modeer.dump          # should list nine TABLE DATA entries
```

This was verified against an archive produced by `backup.ps1`. Note the reason
the passphrase is *mounted and read by openssl* rather than piped in: PowerShell
appends a carriage return to piped stdin, which silently became part of the
passphrase and produced archives that only decrypted from PowerShell. If you
change how the passphrase reaches openssl, re-run the check above.

For a real recovery, restore to a **new database**, never over the live one:

```sh
docker compose --env-file deploy/.env -f deploy/compose.yml exec db createdb -U modeer modeer_restore
docker compose --env-file deploy/.env -f deploy/compose.yml ps -q db
# Use that container ID:
docker cp PATH_TO_BACKUP.dump CONTAINER_ID:/tmp/restore.dump
docker compose --env-file deploy/.env -f deploy/compose.yml exec db pg_restore -U modeer -d modeer_restore --no-owner /tmp/restore.dump
```

Point a separate test backend at modeer_restore, verify record counts, log in and inspect restored conversations. Switch the live database only during an explicitly planned recovery.

For local SQLite, backend/backup_sqlite.py uses SQLite's online backup API and integrity_check; it refuses overwriting. The isolated journey database was snapshotted and reopened with matching user/message/memory counts.

### Verified on 2026-09-10

The whole stack was built and run locally with `DOMAIN=localhost`, which makes
Caddy issue an internal certificate instead of going to Let's Encrypt:

- both images build;
- `alembic upgrade head` applies the initial schema to PostgreSQL 16, creating
  all nine tables — previously only ever run against SQLite;
- the documented bootstrap works end to end: database alone, migrate, provision,
  merge the digest, bring the stack up;
- HTTPS through Caddy: `/api/health` reports `environment: production`,
  `/api/goals` is 401 anonymously, `/api/auth/status` reports `required: true`,
  and the frontend shell serves;
- login returns a `Secure`, `HttpOnly` cookie that authenticates subsequent
  requests;
- **streaming is not buffered by Caddy** — a live reply arrived as 288 SSE
  events spread over 0.95s with 40 gaps above 10ms. Worth testing this way
  rather than with the mock provider, which emits every event within the same
  millisecond and so proves nothing either way;
- data and sessions survive `docker compose down` / `up`: row counts unchanged
  and the existing cookie still authenticated, so a redeploy does not sign
  everyone out;
- `backup.ps1` and `restore-check.ps1` run end to end — dump, archive
  verification, AES-256 encryption, off-host copy, retention, then decrypt and
  restore into a scratch database with matching row counts.

### Still not verified

- **TLS for a real domain.** Let's Encrypt needs a public hostname, so only
  Caddy's internal CA has been exercised. This can only be tested on the real
  host.
- **Restoring over a populated database.** Only restores into an empty scratch
  database have been rehearsed.

### Windows: run these from PowerShell

Git Bash rewrites POSIX paths before they reach Docker, so
`docker cp modeer-provision:/tmp/invite.json .` fails with a mangled
`C:/Users/.../Temp/invite.json`. Either run the bootstrap from PowerShell, or
prefix the command with `MSYS_NO_PATHCONV=1`. The same applies to any
`docker compose exec` that names a container-side path.

The backup scripts must run from PowerShell — they are PowerShell.

## Updates and rollback

Take a backup first. Build the new images and record the source commit. Apply migrations before application startup (the backend container does this). Keep previous images until the new version passes smoke tests. Do not automatically downgrade a production database; rehearse schema rollback or restore on a copy.

The desktop app remains in local development mode until you explicitly configure production. Existing local data has not been converted into shared accounts.

