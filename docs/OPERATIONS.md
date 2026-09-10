# Running Modeer

What to schedule, what to watch, and what happens when it breaks. Written for
the person holding the pager, which on a private deployment is the person who
built it.

Deployment itself is in [DEPLOYMENT.md](DEPLOYMENT.md).

## Scheduled jobs

Nothing here runs itself. A backup script nobody scheduled is not a backup.

On the Linux host, as a user in the `docker` group:

```cron
# Back up at 03:15, then immediately prove the archive restores.
15 3 * * *  MODEER_BACKUP_PASSPHRASE_FILE=/etc/modeer/backup.key \
            MODEER_BACKUP_OFFHOST=/mnt/offsite/modeer \
            /srv/modeer/deploy/backup.sh >> /var/log/modeer-backup.log 2>&1
45 3 * * *  MODEER_BACKUP_PASSPHRASE_FILE=/etc/modeer/backup.key \
            /srv/modeer/deploy/restore-check.sh >> /var/log/modeer-backup.log 2>&1
```

Both exit non-zero on failure, so cron mails you. **Verify the mail arrives** —
send yourself a deliberate failure once (rename the passphrase file and let the
job run) rather than assuming.

`deploy/backup.ps1` and `deploy/restore-check.ps1` are the Windows equivalents,
for a workstation. They are not what production runs.

**Run them on the host, never inside a container.** The encryption step mounts
the backup directory into a helper container, and `docker run -v` paths are
resolved by the *host* daemon: from inside a container the path is the
container's, the host has no such directory, and openssl silently reads an
empty mount. A cron entry on the host is the intended arrangement.

### What has been verified, and what has not

The PowerShell pair has been run end to end on Windows: dump, archive
verification, AES-256 encryption, off-host copy, retention, then decryption and
restore into a scratch database with matching row counts — including a
populated-database rehearsal. An archive also decrypts with stock `openssl`
and restores with stock `pg_restore`, using none of this repository's code.

The shell pair has had its dump, copy and archive-verification steps exercised
and produce a valid ten-table archive. **Its encryption and off-host steps have
not been run on a real Linux host** — only from inside a container, where the
mount cannot work for the reason above. Run both once by hand on the host before
trusting the cron entry, and confirm `restore-check.sh` prints
`RESTORE CHECK PASSED`.

| Setting | Default | Notes |
|---|---|---|
| `MODEER_BACKUP_PASSPHRASE_FILE` | unset | Without it the archive is unencrypted and the script says so on stderr. Store the passphrase somewhere the backup host cannot reach — a passphrase kept beside the backup protects nothing. |
| `MODEER_BACKUP_OFFHOST` | unset | A backup on the same disk as the database is not a backup. |
| `MODEER_BACKUP_KEEP_DAYS` | 30 | Older archives are deleted. |

## The dashboard

`GET /api/admin/dashboard` — one server-rendered page: status, request counts by
status class, unhandled errors with the latest incident id, provider rate-limit
and quota state, and every account's token spend today against its budget.
`GET /api/admin/metrics` is the same data as JSON.

Both are gated on `ADMIN_ACCOUNTS`, a list of account ids. **Empty means nobody**,
not everybody — the page shows other people's usage. Non-admins get 404 rather
than 403, because an operator page should not confirm its own existence.

```sh
ADMIN_ACCOUNTS=["01f2...","03a9..."]      # account ids, from provision_user.py
```

It cannot tell you the app is down: a page served by the app is proof the app is
up. That is what the watchdog below is for.

## Alerts

Set at least one channel, or nothing will ever reach you. Both are free.

```sh
# Any webhook that accepts JSON: Discord, Slack, ntfy
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Or Telegram: talk to @BotFather for a token, @userinfobot for your chat id
ALERT_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
ALERT_TELEGRAM_CHAT_ID=987654321
```

The app alerts on:

| Event | Severity | Why it matters |
|---|---|---|
| Unhandled errors reaching `ALERT_ERROR_THRESHOLD` (default 3) | critical | Something is broken and users are seeing it |
| Provider daily quota exhausted | critical | Replies fail for **everyone** until the budget refills |
| Modeer down or degraded (from the watchdog) | critical | The app cannot report this itself |

The same event alerts at most once every 15 minutes, so a crash loop is one
message rather than three hundred. Alerts carry event names, counts, exception
types and route templates — **never message content**, because they land in a
chat app.

**Send a test alert the day you set this up:**

```sh
curl -X POST https://your-domain/api/admin/test-alert -H "Cookie: modeer_session=..."
```

An alerting path nobody has exercised is a guess, and the day you find out is
the day it mattered.

## Detecting downtime

The app alerts on its own errors. It cannot alert on its own death — a stopped
process sends nothing. `deploy/watchdog.sh` is the outside check:

```cron
*/5 * * * * MODEER_URL=https://your-domain             ALERT_WEBHOOK_URL=https://...             /srv/modeer/deploy/watchdog.sh >> /var/log/modeer-watchdog.log 2>&1
```

It alerts only on a **change** of state, so an outage is one message and its
recovery is another.

Where you run it decides what it catches:

- **On the app host** — catches the container dying, the app hanging, the
  database being unreachable. Not the host dying or losing its network.
- **Somewhere else** — a second small VPS, a home machine, or a free uptime
  service pointed at `/api/health` — catches those too.

Running it on the app host is far better than nothing and takes one line. A
second copy elsewhere is what makes it complete. Both are free.

## What to watch

`GET /api/health` — liveness. `GET /api/health/detail` — readiness plus what the
process has seen: uptime, request counts by status class, unhandled errors, and
the applied schema revision. Both are public, deliberately: an uptime check that
needs a credential is one more thing to break at 3am.

Point any external uptime checker at `/api/health` and alert on:

- **not 200, or unreachable** for two consecutive checks;
- `"status": "degraded"` — the database is unreachable, or unhandled errors have
  accumulated;
- `schema_revision` not matching the revision you deployed. This catches the
  failure where a stale image migrated to its own idea of head and the app is
  running against a schema it does not expect.

An external checker matters more than anything in-process: a server that has
stopped answering cannot tell you it has stopped answering.

## When a user reports an error

Every unhandled failure gives the user a six-character incident id and writes it
to the log:

```sh
docker compose -f deploy/compose.yml logs backend | grep incident=a83a69
```

The log line has the route template, the exception type and the traceback. The
user's message content is never logged, so the log will not tell you what they
asked — that is deliberate, and the incident id plus the route is normally
enough.

## Recovery expectations

Single host, single database, no replica. Be honest about what that means:

| | Expectation |
|---|---|
| **Recovery point** (data you can lose) | Up to **24 hours** — the gap between nightly backups. |
| **Recovery time** (how long to get back) | **1–2 hours**, assuming a working host and a verified archive: provision, restore, migrate, start. Longer if the host itself must be rebuilt. |
| **Tolerated failure** | Loss of the application, the database, or the host — provided an off-host archive exists. |
| **NOT tolerated** | Loss of the off-host archive *and* the host together. There is no second site. |

To shorten the recovery point, back up more often; the job is cheap. To shorten
recovery time meaningfully you need a warm standby, which is a different
architecture and not what this is.

**Rehearse it.** `restore-check.sh` proves the archive restores into an empty
database every night. Restoring *over* a populated database is the case that
matters in a real recovery and is rehearsed separately with
`restore-check.ps1 -RehearseOverwrite`, which mutates a scratch copy, restores
over it, and asserts every table matches the archive again.

## Access and revocation

| Situation | Action |
|---|---|
| Lost device | The user calls `POST /api/auth/sign-out-everywhere`. Ends their sessions only. |
| Access key leaked or lost | `python provision_user.py --rotate --email … --output new-key.json`. New key, sessions ended, one account affected. **Remove the old `AUTH_ACCESS_KEYS` entry** — adding the new one beside it leaves the leaked key working. |
| Signing secret suspected | Rotate `AUTH_SECRET`. This signs out **every** account at once. |
| Someone leaves | Delete their account (theirs to do), then remove their `AUTH_ACCESS_KEYS` entry. |

Removing an entry from `AUTH_ACCESS_KEYS` invalidates that account's live
sessions immediately, because the key digest is part of the session signature.

## Updating

Take a backup first. Build the image, record the source commit, apply migrations
before the app starts — the compose backend does this on boot — and keep the
previous image until the new one has passed a smoke test. Do not automatically
downgrade a production database; rehearse a schema rollback on a copy.

**Always rebuild before migrating.** `docker compose run backend alembic upgrade
head` runs the migrations inside the image, not the ones in your working tree; a
stale image migrates to its own head and reports success.
