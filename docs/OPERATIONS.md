# Running Fareeq

What to schedule, what to watch, and what happens when it breaks. Written for
the person holding the pager, which on a private deployment is the person who
built it.

Deployment itself is in [DEPLOYMENT.md](DEPLOYMENT.md).

## Scheduled jobs

Nothing here runs itself. A backup script nobody scheduled is not a backup.

One exception runs inside the backend: every hour it deletes incognito chats
older than 24 hours (`app/main.py`, `sweep_incognito`). It needs no setup. With
more than one backend process, each runs the sweep; that is harmless.

Install Docker Compose, host `openssl`, `flock`, coreutils, Python 3 and curl.
Run as a dedicated operator with Docker access. Create a private, operator-owned
`/etc/modeer/operations.env` (mode 600), containing shell-quoted assignments:

```sh
MODEER_BACKUP_PASSPHRASE_FILE='/etc/modeer/backup.key'
MODEER_BACKUP_OFFHOST='/mnt/offsite/modeer'
MODEER_BACKUP_KEEP_DAYS='30'
MODEER_URL='https://your-domain'
MODEER_WATCHDOG_STATE='/var/lib/modeer/watchdog.state'
ALERT_WEBHOOK_URL='https://your-real-alert-endpoint'
```

Create the state directory with operator-only write access. Keep a nonempty,
private passphrase file on the backup host so scheduled encryption can run, and
keep a recovery copy in a separate password manager. The backup destination must
already exist and be writable. Verify it really is remote storage and that its
mount is present before scheduling; a second directory on the same disk does
not protect against host loss.

Each cron job below is **one physical line**. The nightly wrapper runs restore
verification on the copied archive only after backup succeeds. Failure sends a
content-free alert through the configured channel and exits nonzero. Logs are
redirected, so cron email is not the alerting mechanism.

```cron
15 3 * * * /bin/sh -c 'set -a; . /etc/modeer/operations.env; set +a; exec /srv/modeer/deploy/nightly-backup.sh' >> /var/log/modeer-backup.log 2>&1
*/5 * * * * /bin/sh -c 'set -a; . /etc/modeer/operations.env; set +a; exec /srv/modeer/deploy/watchdog.sh' >> /var/log/modeer-watchdog.log 2>&1
```

Run the wrapper manually first and confirm `NIGHTLY BACKUP AND RESTORE PASSED`.
Test a failure using a separate invocation with a nonexistent key path and
confirm the notification actually reaches the operator. An accepted webhook is
not proof someone received or read it. Configure log rotation on the host.

Linux backups now refuse missing encryption keys or destinations **before
creating a dump**. They encrypt using native OpenSSL, compare the copied bytes,
remove transient plaintext, and expire matching archives on **both destinations**
after 30 days (configurable). Overlapping backup jobs are rejected. Restore uses
a unique scratch database and removes it afterward. The Linux scripts are stored
with executable Git permissions and LF line endings.

A Linux-container rehearsal with PostgreSQL 16 has verified encryption, copy,
decryption, restore, missing-key rejection, wrong-key rejection, local/copied
retention, readiness monitoring, recovery, and failed-delivery retries. See
`linux-operations-results.json`. The copied directory in this rehearsal is on the
same development machine: real off-host durability and the production scheduler
still need verification on the chosen host. Object-store version history and
snapshots require their own matching retention policy.

The PowerShell scripts are workstation helpers, not the production scheduler.
Their older behavior does not define the guarantees above.

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
| Provider daily quota exhausted | critical | Replies using the affected model may fail until its budget refills |
| Fareeq down or degraded (from the watchdog) | critical | The app cannot report this itself |

The same event alerts at most once every 15 minutes, so a crash loop is one
message rather than three hundred. Alerts carry event names, counts, exception
types and route templates — **never message content**, because they land in a
chat app.

**Send a test alert the day you set this up:**

```sh
curl -X POST https://your-domain/api/admin/test-alert -H "Cookie: modeer_session=..."
```

The endpoint returns 502 if no channel accepts the test; it reports success only
after an endpoint accepts delivery. Confirm the message also reaches the person.

## Detecting downtime

The app alerts on its own errors. It cannot alert on its own death — a stopped
process sends nothing. `deploy/watchdog.sh` is the outside check:

Use the single-line watchdog cron entry above, with its private environment file.

It alerts only on a **change** of state, so an outage is one message and its
recovery is another. A failed notification leaves the prior state unchanged so
the next check retries delivery.

Where you run it decides what it catches:

- **On the app host** — catches the container dying, the app hanging, the
  database being unreachable. Not the host dying or losing its network.
- **Somewhere else** — a second small VPS, a home machine, or a free uptime
  service pointed at `/api/health/detail` — catches those too.

Running it on the app host is far better than nothing and takes one line. A
second copy elsewhere is what makes it complete. Both are free.

## What to watch

`GET /api/health` — liveness. `GET /api/health/detail` — readiness. Both answer
anyone, deliberately: an uptime check that needs a credential is one more thing
to break at 3am. Since 2026-09-13 an anonymous caller gets only what a check
needs — `status`, `database`, `schema_current` (liveness: `status`, `database`)
— and the HTTP status. Sign in as an account listed in `ADMIN_ACCOUNTS` and open
`/api/health/detail` in the browser for the rest: uptime, request counts by
status class, unhandled errors, recent incident ids, provider counters and both
schema revisions. `watchdog.sh` reads only `status`, so it is unaffected.

Point any external uptime checker at `/api/health/detail` and alert on:

- **not 200, or unreachable** for two consecutive checks;
- `"status": "degraded"` — the database is unreachable, or unhandled errors have
  recently accumulated, or an observed provider quota block is active, or a
  model has failed several requests in a row (see below);
- `"schema_current": false` — the database is not at the migration head this
  build expects. Readiness reports both sides to admins: `schema_revision` is what the
  database is at, `expected_schema_revision` is what the running code was built
  against. This catches the failure where a stale image migrated to its own idea
  of head and the app is running against a schema it does not expect.

Readiness returns HTTP 503 when degraded, including, in production, a database
that is not at the expected head. The expected head is read from the migration
scripts inside the image, so shipping a new migration moves it automatically —
nothing to edit by hand. It was once a literal `0003`, which would have made the
next migration report a healthy app as degraded indefinitely. Branched histories
need every head applied. If the scripts cannot be read, production fails closed. Historical quota counters do not permanently mark the app down:
a successful response from the affected model clears its block, or it expires
after the provider’s retry interval. Readiness observes actual requests; it does
not send a synthetic AI request or guarantee unused provider credentials work.

**Transient and sustained provider failures are separate** (changed 2026-09-11).
A single timeout, dropped stream or 5xx is weather: the person who saw it gets a
labelled reply and a Try again button, and readiness stays ok. It is still
visible — `provider.failures` counts every one and `provider.failure_streaks`
shows each model's current run of consecutive failures. Readiness degrades only
when one model fails `PROVIDER_FAILURE_STREAK` (3) requests in a row with no
success between; it then stays degraded for ten minutes after the latest
failure, longer than the watchdog's five-minute cadence, and any success clears
it at once. Throttling is not a failure: a per-minute 429 only moves
`provider.rate_limits`, and a daily-quota 429 is the quota block above, which
still degrades readiness and still sends its own alert. Database and schema
problems are checked separately and are never softened by any of this.
Constants: `app/core/observability.py`.

An external checker matters more than anything in-process: a server that has
stopped answering cannot tell you it has stopped answering.

## When a user reports an error

Every unhandled failure gives the user a six-character incident id and writes it
to the log:

```sh
docker compose -f deploy/compose.yml logs backend | grep incident=a83a69
```

The log line has the route template, exception type and stack locations, without
exception values, SQL parameters, source text, or chained exception messages.
Production Uvicorn access logs are disabled; the application logs route templates. The
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
| Lost device | Account → Sign out every device. Ends their sessions only. |
| Password forgotten | Login → "Forgot your password? Use a recovery code". Each code works once; the Account page makes a fresh set. Sessions elsewhere end. |
| Password and every recovery code lost | No self-service way back — by design there is no email reset. After confirming who they are by a channel you trust: `python provision_user.py --rotate --clear-password --email … --output key.json`, merge the entry into `AUTH_ACCESS_KEYS`, restart, hand over the key. That removes their password and codes and ends their sessions; they sign in with the key and set a new password on the Account page, which issues fresh codes. |
| Password suspected known to someone else | Account → change password. Every other session ends. |
| Repeated sign-in or signup attempts | Already limited: 10 password attempts per email per 15 minutes, 5 signups per client address per hour, both answering 429. The counters live in `usage_buckets`, hashed. |
| Access key leaked or lost | `python provision_user.py --rotate --email … --output new-key.json`. New key, sessions ended, one account affected. **Remove the old `AUTH_ACCESS_KEYS` entry** — adding the new one beside it leaves the leaked key working. |
| Signing secret suspected | Rotate `AUTH_SECRET`. This signs out **every** account at once. |
| Someone leaves | Delete their account (theirs to do), then remove their `AUTH_ACCESS_KEYS` entry. |
| Account being abused, or needs pausing | Signed in as an operator (`ADMIN_ACCOUNTS`): `POST /api/admin/accounts/{id}/suspend`. Their sessions end, sign-in answers 403 "This account is suspended", and chat stops. Nothing is deleted. `POST …/unsuspend` restores it. An operator cannot suspend themselves. |

Removing an entry from `AUTH_ACCESS_KEYS` invalidates that account's live
sessions immediately, because the key digest is part of the session signature.
Password-only accounts have no entry; their sessions end through the account's
session generation (password change, recovery, sign out everywhere) or deletion.

## Updating

Take a backup first. Build the image, record the source commit, apply migrations
before the app starts — the compose backend does this on boot — and keep the
previous image until the new one has passed a smoke test. Do not automatically
downgrade a production database; rehearse a schema rollback on a copy.

**Always rebuild before migrating.** `docker compose run backend alembic upgrade
head` runs the migrations inside the image, not the ones in your working tree; a
stale image migrates to its own head and reports success.

## Voice and photos

- **Voice input** needs `LLM_PROVIDER=groq`. It uses Groq's free Whisper
  endpoint (`TRANSCRIBE_MODEL`, default `whisper-large-v3-turbo`) with the same
  key. Each account gets 60 transcriptions a day (`VOICE_PER_DAY`), each at most
  4 MB (`VOICE_MAX_BYTES`, about a minute). Groq limits audio separately from
  text: when it says no, people see "Voice input is at its limit for now".
  `VOICE_ENABLED=false` hides the mic.
- **OCR** needs the `tesseract` program and `models/tessdata/{ara,eng}.traineddata`.
  The image has both. On a development machine, install Tesseract (`brew install
  tesseract`) and run `python -m app.documents.fetch_ocr`. Without them, photo
  uploads fail with "Reading text from photos isn't set up on this server".

