# Local production rehearsal — 2026-09-14

**Closeout updated 2026-09-15.** The live application journey passed 13 checks.
The complete quality run produced 39 responses: 27 automated passes, 11 failures
and one unavailable grade. Retrying the unavailable grade did not produce valid
JSON. See [quality results and adjudication](quality-evidence-2026-09-15.md).

Release status: **not yet approved for public production**. This pass closes
local production-image, PostgreSQL recovery-race, current-schema backup and
HTTPS browser checks. Public-domain deployment, real remote storage, human
alert receipt and physical-device checks remain unverified. No frontend design
was changed in this pass.

## Environment and evidence boundaries

Working tree based on `1ed17eb5748d948a541f0e76a7fabcddd094534d`, including
the September 13–14 fixes. Docker Desktop was installed under the user's local
Programs directory; starting that installation resolved the previous engine
connection failure. Tests used the isolated Compose project
`modeer-rehearsal-20260914`, PostgreSQL 16, the actual production Dockerfiles,
and the repository Caddy configuration. Only localhost port 8443 was exposed.
Credentials, accounts, model replies and database contents were synthetic.
Image identities and detailed limitations are in
[verification metadata](production-verification-2026-09-14.json).

The frontend built with Node 22 and Next.js 16.3.5 in its production image.
The backend's 33 installed runtime dependencies exactly matched the hashed
lockfile, without extra runtime packages other than pip. Test tools were
installed separately under `/tmp/testtools` in an ephemeral container.

## Completed verification

- **351 backend tests passed** in the final production image. Most use SQLite;
  the two simultaneous-recovery tests used PostgreSQL with a unique temporary
  schema per case. The same recovery code yields one success and one rejection;
  different codes yield successful sessions at epochs 1 and 2. This is evidence
  for these races, not a multi-worker load test of every endpoint. One existing
  Starlette TestClient deprecation warning remains. Ruff passed locally.
- **23 HTTPS browser checks passed:** secure cookies, per-request CSP nonces,
  ten rendered pages, onboarding and saved context in a specialist prompt,
  progressive streaming through Caddy (14 visible steps), truncated/interrupted
  replies, retry without duplicates, offline recovery, safe links, blank input,
  deletion, account isolation, revocation, announcements, memory conflicts,
  readiness disclosure, signup, password login, consent, recovery and 390px layout.
  [Raw browser results](production-rehearsal-2026-09-14.json).
- **25 automated accessibility scans reported zero findings**, covering desktop
  and phone-width pages, invitation login and recovery-code acknowledgement.
  Keyboard navigation and signup-to-first-message also passed.
  [Raw accessibility results](accessibility-rehearsal-2026-09-14.json).
  This is desktop Chrome emulation and axe, not a physical phone or human
  assistive-technology pass.
- PostgreSQL migration rehearsal: empty database to `0004`, downgrade to `0003`,
  then upgrade to `0004`. A sentinel user's identity and session epoch survived;
  the recovery table was recreated. **Downgrade deletes password/recovery data**;
  it is not a data-preserving production rollback. Use a tested backup.
- Direct backend requests to `/docs`, `/redoc` and `/openapi.json` returned 404,
  independently of Caddy routing.
- **Ten operations checks passed:** encryption prerequisites, retention and
  plaintext cleanup, wrong-key rejection, restore from the copied archive,
  outage/recovery state changes, retry after failed alert delivery, backup-failure
  alerts, nightly backup/restore, and unreachable-app detection. The expanded
  restore check compared every table's count and deterministic row digest with
  the source at schema `0004`, including password hashes, consumed recovery codes,
  session epochs and consent. A clean restore over an already populated scratch
  database also recovered the exact source rows. [Operations results](operations-rehearsal-2026-09-14.json).
- Read-only audit of the configured existing local SQLite database found zero
  automatic shared/private memories to inspect. This does not audit other
  databases or prove older overwritten/widened records never existed.

The operations receiver was a local synthetic HTTP server; no messages were
sent to a real operator. The “offhost” destination was deliberately a second
directory on this computer. It proves copying and restoration, not host-loss
protection or scheduled execution. The initial disposable worker omitted curl;
adding the documented dependency fixed that rehearsal setup failure.

## Agent changes and quality gate

Study and Research now target shorter plans; Study checks mastery thresholds and
avoids invented exercise numbers. Fitness checks equipment by day and preserves
weekly frequency. Shopping no longer instructs the model to claim unknown
products fit a budget. Travel forbids invented departure times. Writing omits
unknown optional bio details instead of requiring unfinished placeholders.
Prompt versions increased for all six specialists; model settings are unchanged.

The judge now explicitly checks unsupported budget/support/schedule claims,
workout counts and equipment, unfinished artifacts, and logical consistency.
Its stricter criteria mean raw pass rates are not directly comparable with
September 13. Passing a judge is never sufficient evidence by itself: manually
review constraint adherence and confirm each quoted failure is valid.

The [final dated quality evidence](quality-evidence-2026-09-15.md) records the
complete run and manual spot checks, including false positives and missed defects.
The first one-row partial was intentionally stopped when a conflicting Writing
configuration instruction was found; it is preserved as historical evidence.

## Reproduction

Use the [browser rehearsal instructions](../deploy/tests/production-rehearsal/README.md)
with a fresh isolated project and new report filenames. Do not reset a real
deployment or point the synthetic seed accounts at it.

From the repository root, with Docker running:

```powershell
docker compose -p modeer-rehearsal-20260914 -f deploy/tests/production-rehearsal/compose.yml up -d --build
docker compose -p modeer-rehearsal-20260914 -f deploy/tests/production-rehearsal/compose.yml exec -T -e PYTHONPATH=/app backend python /rehearsal/seed_users.py
# Set PLAYWRIGHT_MODULE if needed and REHEARSAL_REPORT to a NEW output file.
node deploy/tests/production-rehearsal/browser-check.cjs
```

For the locked-image suite, mount `backend/tests` and
`deploy/tests/image-check.sh` as documented in that script. Attach the container
to `modeer-rehearsal-20260914_default` and set `RECOVERY_TEST_POSTGRES_URL` to
`postgresql+psycopg://modeer:rehearsal-only@db:5432/modeer` to run the recovery
races against the disposable PostgreSQL service. Never use a production URL.

Create an otherwise empty scratch database named `modeer_migration_20260914`,
set the migration-check container's `DATABASE_URL` to it, `LLM_PROVIDER=mock`
and `PYTHONPATH=/app`, and mount/run
[postgres-migration-check.py](../deploy/tests/postgres-migration-check.py).

For operations, run `docker:cli` with the Docker socket, a read-only `deploy`
mount at `/source`, and a fresh temporary directory at `/qa`. Run
[operations-rehearsal.sh](../deploy/tests/operations-rehearsal.sh). It targets
only the dated rehearsal project above, installs worker dependencies, and calls
the actual backup/watchdog scripts plus
[linux-rehearsal.py](../deploy/tests/linux-rehearsal.py). Finish by stopping the
dated Compose project. These test credentials must never be deployed publicly.

## Remaining owner and release gates

1. Resolve measured answer-quality defects and adjudicate judge disagreements;
   select release acceptance criteria and sustainable provider capacity.
2. Select the host/domain and rehearse the real public certificate, cookies,
   account separation and interrupted streaming there.
3. Provision genuinely remote encrypted backup storage, verify mount failure
   behavior and retention, install the scheduler and restore from that storage.
4. Configure a real alert recipient and confirm outage, recovery, test and
   backup-failure receipt with explicit authorization to send those messages.
5. Complete physical iPhone/Android and human screen-reader journeys.
6. Confirm signup mode, automatic-memory default, data-retention/recovery goals,
   privacy/support responsibility and documented artwork usage rights. Audit any
   other database that contains pre-fix memories.

The recommended next release milestone is a private hosted staging rehearsal,
alongside the remaining targeted quality remediation. Native mobile development
and a public announcement should wait for those gates.

## September 15 environment closeout

The live journey finished successfully and removed its scratch SQLite database.
At documentation closeout the Docker engine was unavailable; a bounded startup
attempt did not restore connectivity and was stopped. Consequently, removal of
the dated disposable Compose containers/volumes was not verified. Once Docker
is available, inspect the project label `modeer-rehearsal-20260914` and remove
only that synthetic rehearsal project. Do not reset another project or a real
deployment. The September 14 completed test evidence remains valid for the
recorded images/configuration; it is not a claim that the services are running now.
