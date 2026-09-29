# Rollout: review fixes and migration 0013

Covers the twelve-feature batch (migration 0012) and its review fixes
(migration 0013). A server still on 0011 takes both in one upgrade.

## What changes for people

- **Reminders must be switched on again, once.** Migration 0013 deletes every
  existing reminder subscription: older ones were not tied to a signed-in
  device, so they could not be ended by signing out. After the update each
  person turns them on again under Account › Reminders, on each device where
  they want them. Nothing else they saved is affected.
- From then on, signing out of a device (or removing it, signing out
  everywhere, recovering the account, or changing the password on another
  device) stops that device's reminders.

## Steps on the server

1. **Back up first**, and check the backup restores:
   `./deploy/backup.sh` then `./deploy/restore-check.sh`.
2. Pull the release and **rebuild before starting** (a stale image migrates to
   its own head and reports success):
   `docker compose -f deploy/compose.yml build`
3. Start it; the backend applies migrations on boot:
   `docker compose -f deploy/compose.yml up -d`
4. Confirm the schema: `docker compose -f deploy/compose.yml exec backend alembic current`
   shows `0013 (head)`.
5. Smoke test: sign in, open Plans, save a quick note, open Account and turn on
   reminders on one device, press "Send a test".
6. Tell people (below).

**Rollback.** Do not downgrade the production database automatically. If the
release must be withdrawn, restore the step-1 backup into the previous image.
Downgrading 0013 on a copy works (verified) but reminders switched on after
the upgrade are lost either way.

## Message to people

> **Reminders need turning on again.** We made reminders safer: they now stop
> as soon as you sign out of a device. Because of that, reminders you had on
> were switched off in this update. To get them back, open **Account ›
> Reminders** on each device and tick "Send me a daily reminder on this
> device". Nothing else has changed.

> **أعد تفعيل التذكيرات.** جعلنا التذكيرات أكثر أمانًا: تتوقف الآن فور تسجيل
> خروجك من الجهاز. لذلك أُوقفت التذكيرات المفعّلة في هذا التحديث. لاستعادتها،
> افتح **الحساب › التذكيرات** على كل جهاز وحدّد «أرسل لي تذكيرًا يوميًا على هذا
> الجهاز». لم يتغيّر شيء آخر.

## Verified before release (2026-09-28)

### Mobile preparation follow-up (2026-09-29)

- Browser chat drafts are now account-bound and cleared on API authentication
  loss, including upload/stream paths. Previously stored drafts without a
  verified owner are discarded on first activation. Same-account drafts survive
  reloads; stale callbacks cannot restore a cleared draft.
- Talk cannot start during a pending reply/upload. Speech arriving while
  sending is unavailable is retained in the editable composer.
- Replies over 1,500 characters use the complete device voice rather than a
  truncated natural-voice request; no extra provider calls are introduced.
- Frontend unit tests: 24/24. Isolated production build and TypeScript passed.
  Targeted lint: zero errors, 12 existing warnings. Chrome regression: 66/66,
  using a disposable mock API/database and a build excluding private environment
  files. Includes revoked-session draft cleanup and pending-reply Talk disabling.
- Browser sign-in QA now waits for the client auth-status response before
  clicking, avoiding clicks on an unhydrated server-rendered form.
- No production deployment or commit was made. The compatibility gaps listed
  below remain open; these results do not verify a native application.

### Production-audit fixes (2026-09-29)

- Caddy permits the app's own microphone (`microphone=(self)`); camera and
  other disabled capabilities stay disabled. The deployment guide agrees.
- Backend Docker exclusions cover database files, journals, SQLite files,
  backup suffixes and backup directories at both root and nested paths.
- Talk mode appends speech to existing typed work, or to an unsent composer
  with staged files, and exits without sending. Attachments remain staged.
- A late account lookup preserves incoming handoffs and early typing. Ordinary
  owned drafts still restore after reload.
- CV edits are stored as account-bound recovery drafts per CV, restored on
  returning/reloading, and cleared on save, deletion or authentication loss.
  Explicitly discarding a version clears its recovery draft. A recovery notice
  distinguishes local edits from saved server data. The reload/close warning
  cannot obstruct authentication cleanup.
- Test reminders have a database-backed limit of three attempts per account
  per minute, with HTTP 429 and Retry-After; rejected attempts do not send push.
- Verification: backend 573 passed, 1 skipped; frontend unit tests 24 passed;
  Chrome review suite 74/74 passed. After the final CV warning safeguard, four
  focused browser checks passed for navigation, recovery notice, reload and
  expired-session cleanup. Final isolated production build and TypeScript
  passed. Targeted backend lint passed; frontend lint had zero errors and seven
  warnings in ChatWorkspace.
- The browser tests used disposable mock data and no real provider or push
  delivery. Docker was not running, so image-layer inspection and live Caddy
  verification remain staging gates, alongside real-device microphone,
  push/logout, PostgreSQL migration/restore and telemetry verification.
- The audit's lower-priority subscription-renewal handling and SQLite
  startup/migration workflow are not changed by this six-fix batch.
- No commit, production migration or deployment was performed.

### Earlier release verification

- Follow-up: application startup now forces `ORT_DISABLE_TELEMETRY=1` before
  ONNX Runtime imports. The API-only opt-out can miss initialization events.
  A fresh-process regression test covers an explicitly enabled inherited
  setting; five additional native import/exit probes exited successfully.
  This does not establish the cause of the previously reported exit crashes.
- Follow-up backend suite: 570 passed, 1 skipped; backend lint passed.
  Three consecutive repeat runs also passed with clean process exits. Frontend
  unit tests passed 21/21. These checks do not prove the previous crash's cause.
- Follow-up Chrome review regression passed 63/63 against a clean disposable
  mock database and the existing production frontend build, including Arabic
  and English drawers at 150% on mobile. Its positive speech test now waits
  for the new speech request rather than counting pre-existing replies; the
  25-second timeout and exactly-one-send assertion are unchanged.
- Compatibility remains incomplete: Firefox could not open its temporary
  profile; WebKit stalled and was stopped; the desktop live-push test could
  not enable the reminder checkbox. None is recorded as a pass. Real-device
  push/logout and a real microphone still require verification.
- Local SQLite migration 0013 was applied after creating a consistent SQLite
  backup and successfully migrating a restored copy. Integrity and foreign-key
  checks passed. No production deployment was performed.

- Migrations 0001–0013 on PostgreSQL 16.15 (the pinned `postgres:16-alpine`
  image): legacy subscriptions removed, both foreign keys cascade, a device
  deleted takes its subscriptions, the receipt key is unique, downgrade and
  re-upgrade clean. Also on SQLite.
- Two saves of one quick note at the same moment store it once, on PostgreSQL
  and SQLite (`tests/test_twelve_feature_fixes.py`, with
  `RECOVERY_TEST_POSTGRES_URL` set).
- `alembic check` against PostgreSQL reports two older differences, not from
  this release: `conversations.last_message_at` and `goals.target_date` are
  timezone-aware in the migrations and plain `DateTime` in the models (since
  the first commit). Harmless today; worth a migration of their own.
