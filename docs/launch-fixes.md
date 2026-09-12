# Launch fixes and verification — 2026-09-11

The repository fixes below are implemented. Public production is not signed off.
No deployment or main-branch merge was performed. The approved comic design and
character artwork are unchanged.

## Application fixes

- Account export handles the stored briefing date string; it previously failed
  after a briefing existed.
- Account lets users download their data, sign out every device, or permanently
  delete their account after typing DELETE. The public privacy notice is linked
  from login and Account. Conversation history has a confirmed deletion action.
- Shared preferences now reach specialists. The previous category filter omitted
  them even though evaluation fixtures supplied them directly. Live requests and
  evaluations now use the same filtering function; other specialists' private
  notes remain excluded.
- Exceptions log route templates, incident IDs, types and stack locations without
  exception text, chained values or SQL parameters. Production server access logs
  and HTTP-client URL logs cannot expose private routes or alert credentials.
- Long provider waits are displayed accurately. Readiness returns 503 for active
  quota blocks, recent provider failures, recent repeated server errors, or the
  wrong production schema. Successful replies clear the affected model's state.
  (Refined in the production-readiness pass below: a single provider failure no
  longer degrades readiness; a run of them does.)
- Repeated errors share a stable alert cooldown key. Alert channels are attempted
  independently. An operator test reports failure unless an endpoint accepted it.

## Operations fixes

Linux backups require a key and an existing copy destination, reject overlap,
encrypt with native OpenSSL, compare the copied bytes, clean transient plaintext,
and prune matching archives from both destinations. The nightly job verifies the
copied archive immediately and alerts on failure. The watchdog reads readiness,
not basic liveness, and retries notifications that failed to deliver. Cron recipes
are single physical lines and use a private environment file.

The Linux rehearsal used PostgreSQL 16 at revision 0003, with synthetic user,
briefing and usage-ledger data. It verified encryption/decryption/restore,
missing-key and wrong-key failures, retention on both destinations, degraded and
recovered readiness, delivery retries, and nightly-job failure alerts. Notifications
went only to a local test endpoint. The copied archive was on the same development
machine: this does not prove physical off-host disaster recovery.

## Verification evidence (earlier pass, 2026-09-11 — historical)

Counts in this section are as they were then. Current evidence is in the
production-readiness pass at the end of this file.

- `account-qa-results.json`: nine Chrome checks with an authenticated mock backend,
  including export after a briefing, visible export failure, cancellation and
  deletion, 390/768/1440 layouts, second-device revocation, account deletion and
  rejection of the deleted account's old key. No uncaught browser errors.
- `linux-operations-results.json`: eight Linux operations checks.
- Backend: 154 passing tests and clean Ruff checks.
- Frontend: production build (including type checking) and lint passed.
- Prior everyday-journey evidence remains in `browser-qa.md`; it covers onboarding,
  memory follow-up, offline retry and interrupted streams. It was not rerun against
  the final production frontend in this pass: automatic approval review rejected
  startup with only "blocked by policy". The account checks ran against the
  development frontend. Physical-device and real-domain streaming remain unverified.

## Agent quality

The completed generation reports contain three samples of thirteen cases: ten
personalized specialist/leader tasks plus unknown-fact checks for Study, Career
and Writing. All fixtures are synthetic. Writing retains qwen/qwen3.8-27b; the
other agents use the selected default. Timings measure provider completion in the
harness, not end-to-end browser latency or load capacity.

The original grader did not see the name/profile passed to the agent and could
accept incomplete or nonboolean grades. Version 2 fixes those defects, permits
advice to use an in-app specialist, and retries short grader rate limits. Raw
results are retained. Regrading changes scores, not saved answers. An unavailable
grade is never a pass. A same-model grade for Writing is not independent evidence.

The raw generation reports are:
`quality-production-launch.json` and `quality-candidate-20b-launch.json`.

The 20b candidate, preserving Writing's qwen override, completed 39 responses:
31 passes, 6 failed answers, and 2 unavailable grades. It had no deterministic
length failures. It is **not promoted**: sample 3 Shopping recommended Android
while ignoring the supplied iPhone/Apple Watch context; Fitness invented which
weekdays remained. A manual check also found Finance's sample 3 incorrectly
turning a EUR 40,000 goal over four years into EUR 1,000/month (40,000 / 48 is
about 833.33). These are substantive failures, not formatting preferences.

The configured 120b run initially hit a long provider quota wait after 32 cases;
it was resumed after capacity returned to finish all 39. Eleven answers exceeded
the existing word ceilings. Its raw automated scores include the old grader's
limitations, so use `quality-production-launch-regraded.json` for corrected scores.
The original raw file is retained for traceability. Some judge findings can still
be false positives; inspect the quoted evidence rather than treating a score as
proof. No model setting was changed on the strength of these results.

With the corrected grader, the configured 120b run scored **25/39 passes**,
14 failed answers and 0 unavailable grades. All 39 saved responses were
regraded. This confirms a quality blocker independently of the original quota
interruption. The full corrected evidence is in
`quality-production-launch-regraded.json`.

## Answer-length fix — 2026-09-11 (gate 1)

Eleven of the fourteen regraded failures were `too_long`; the grounding findings
were three. It was one dominant problem, and partly ours rather than the model's:
the prompt said "under 350 words" while `max_tokens` handed the agent 1200–1400
tokens, roughly 900–1050 words. The budget is the louder signal. `max_tokens`
could not be used as a control either, because hitting the cap raised
`ProviderError` and discarded the whole reply — the cap could only destroy an
answer, never shorten one.

Three changes:

- **Truncation is graceful.** Running to the cap now keeps what has already
  streamed and ends the reply; only a cap consumed with nothing emitted is still
  an error. Counted as `length_stops` in readiness so a rising count shows the
  cap fighting the prompt.
- **Caps match the stated ceiling.** Plan agents 1200–1400 → 800, advice agents
  → 650. Comfortably above the 450-word ceiling, far below the previous ~900.
- **Limits the model can count.** At most three headings, one table, one line per
  row or day; no "Why this works", "Downside test" or "Assumptions" block. Those
  sections were exactly what Study and Finance padded with.

Two further conflicts, the same bug class as Writing's rationale rule — a
per-agent instruction contradicting a global rule, which the model resolves by
doing the forbidden thing:

- Travel was told "show the budget split" unconditionally *and* "never invent a
  budget". It invented budgets so it had a split to show. The split is now
  conditional on a budget having been given.
- Travel was told to "note assumptions the user must confirm" while the global
  rule forbids an Assumptions block. It produced one, filled with invented
  personal facts ("You're traveling solo", "flexible budget"). Now scoped to
  external items — visa, weather, seasons — inline, with nothing about the person.

Rule 3 also now covers **which model or version of a thing someone owns**:
Shopping turned "already on iPhone" into "your iPhone 13/14".

### Measured on `openai/gpt-oss-120b`

| | Deterministic | `too_long` | Word range |
|---|---|---|---|
| Before (39 responses, regraded) | 28/39 | **11** | 9–803 |
| After length fix (18 responses) | 18/18 | **0** | 9–428 |
| After travel/shopping fixes (6) | 6/6 | **0** | 229–345 |

With the judge, the 18-response run scored 17/18 and the travel/shopping run
5/6. Every reply ended on a complete sentence — the lower caps shortened answers
by choice, not by truncation.

**Not yet measured:** the owned-model/version rule was added after the last run,
and a full 39-case run directly comparable to the 25/39 baseline did not
complete — the provider's daily budget ran out after four cases. Resume it with
`python quality_check.py --samples 3 --resume` on a fresh budget before treating
gate 1 as closed. (That command omits the judge and output path the run was
started with; the full command, and the resumed run's progress to 27/39, are in
the production-readiness pass below.)

## Pre-production review — 2026-09-11

A fresh read-only review of the whole project looked for problems that were not
already on any list. Baseline at the time: 156 backend tests passing, Ruff clean,
frontend lint, type check and production build clean.

Checked and found sound: every frontend API call matches a real backend route
and HTTP method; CORS allows only `FRONTEND_URL`; no model output reaches the page
as raw HTML and `javascript:` links are neutralised; session cookies are Secure,
HttpOnly and SameSite=Strict; the admin dashboard is closed when `ADMIN_ACCOUNTS`
is empty; the backend container runs as a non-root user; no secrets are tracked.

### Fixed

**1. Readiness hard-coded the schema revision.** `GET /api/health/detail`
compared the database against the literal `"0003"`, so the next migration would
have made production report a healthy app as degraded indefinitely — and a
watchdog that alerts on nothing trains its reader to ignore it. The expected
head is now read at runtime from the migration scripts shipped in the image
(`expected_schema_revisions()` in `backend/app/api/routes/health.py`). Readiness
also reports `expected_schema_revision` and `schema_current`, requires every head
of a branched history, and fails closed in production if the scripts cannot be
read. Seven tests in `backend/tests/test_schema_readiness.py`.

Proved against a real temporary migration `0004`, applied: the old code returned
**503 degraded**; the new code returns **200 ok**. The probe file was removed.

### Open at review time — all resolved in the production-readiness pass below

| # | Severity | Problem | Where | Status |
|---|---|---|---|---|
| 2 | Medium | **Backend builds are not reproducible.** `requirements.txt` has version ranges and no lockfile, so a rebuild can install newer libraries than the tests ran against — `pydantic>=2.7,<3` alone spans many releases. The frontend is locked (`package-lock.json` + `npm ci`). | `backend/requirements.txt`, `backend/Dockerfile` | Fixed: hashed `requirements.lock`, digest-pinned base image |
| 3 | Medium | **Ask My Team is live but unreachable from the UI.** Nothing in `frontend/` calls `/api/team/ask`, yet it is the most expensive route: up to five specialists plus a synthesis per request. It spends shared quota and gives users nothing today. Build the UI or switch the route off until then. | `backend/app/api/routes/team.py` | Fixed: off by default (`TEAM_ENABLED`), implementation kept and tested |
| 4 | Medium | **Readiness can flap on a free tier.** One failed provider call marks the model degraded until its next success, so a single overnight timeout produces a DEGRADED then a RECOVERED notification. Not a bug; watch the alert volume after launch. | `_erroring()` in `backend/app/api/routes/health.py` | Fixed: only a run of failures degrades |
| 5 | Medium | **Specialist isolation is tested at the query, not the prompt.** Tests prove one agent's private notes are not *returned* for another, not that they are absent from the prompt a real chat request builds. The memory filtering function changed on 2026-09-11. | `backend/tests/test_memory.py` | Fixed: `tests/test_prompt_isolation.py` reads the provider's input |
| 6 | Low | **No Content-Security-Policy header.** Rendering is already safe (React elements, no raw HTML), so this is defence in depth. | `deploy/Caddyfile` | Fixed: CSP in Caddyfile, validated in Chrome |
| 7 | Low | **Markdown links allow protocol-relative URLs.** The allowlist `^(https?:\|mailto:\|/)` also admits `//evil.example`. A phishing link, not script injection. | `frontend/src/lib/markdown.tsx` | Fixed: `frontend/src/lib/links.ts` |
| 8 | Low | **API docs are hidden by routing, not disabled.** FastAPI's `/docs` and `/openapi.json` are unreachable only because Caddy forwards `/api/*` alone. Any change that exposes the backend port publishes the full schema. | `backend/app/main.py` | Fixed: disabled when `ENVIRONMENT=production` |
| 9 | Low | **Stale numbers in the docs.** `HANDOFF.md` says 101 tests and nine tables (now 163 and ten); `DEPLOYMENT.md` says nine tables in one place and ten in another. HANDOFF is what another assistant would act on. | `docs/HANDOFF.md`, `docs/DEPLOYMENT.md` | Fixed: current counts, historical ones labelled |

## Production-readiness pass — 2026-09-11 (evening)

**Baseline.** Branch `fixes/launch-readiness-20260911` at `172f857`, with the
uncommitted schema-readiness fix above (`health.py`, `test_schema_readiness.py`,
this file, `OPERATIONS.md`) preserved and built on, not reverted. Configuration
recorded without secrets: `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-120b`,
reasoning effort `low` (default), Writing's `qwen/qwen3.8-27b` override,
`MEMORY_STORE_SENSITIVE` off, local SQLite dev database. Nothing was committed,
merged, pushed or deployed.

### 1. Memory privacy — extraction now fails closed

Revalidated first: automatic extraction had four fail-open paths. An invalid
scope, an unknown specialist id, or a Modeer-private note each fell back to
**shared** memory, which every specialist reads; a non-numeric confidence
became 0.7 and passed the threshold. Automatic extraction could also overwrite a
fact the person had saved by hand (and reset its pin), and the explicit-save
route accepted a client-supplied `source`.

Now (`backend/app/memory/llm_extraction.py`, `service.py`, `sensitivity.py`,
`routes/memory.py`):

- Every candidate is validated field by field — types, scope, category from the
  prompt's vocabulary, key format, value length, confidence as a real number in
  range. Anything malformed is **dropped**, never repaired or widened.
- A private note must name the specialist being talked to (or Modeer); anything
  else is dropped. Invalid private memory is never converted to shared.
- Sensitivity no longer rests on the model's flag alone: a missing, `false`-by-
  omission or non-boolean flag counts as sensitive, and a keyword backstop
  (health, income and balances, identity numbers, credentials, belief,
  sexuality, immigration and criminal status) withholds a fact the model called
  harmless. With `MEMORY_STORE_SENSITIVE` off — the release setting — such facts
  are not stored automatically. The backstop is a floor, **not a classifier**;
  it cannot promise to catch every sensitive fact, and says so.
- Explicit saves are recorded as `source="user"` whatever the client sends, and
  automatic extraction never overwrites them; automatic updates keep pins.

Tests: `test_memory_privacy.py` (53, including malformed-field and unusable-
scope matrices with positive controls), `test_llm_extraction.py` (the test that
asserted the unknown-agent leak now asserts rejection), and
`test_prompt_isolation.py`, which drives real HTTP chat requests and reads the
provider's own input: one specialist's private notes never reach another's
prompt, one account's data never reaches another account's prompt, and each
test carries a positive control proving the marker *does* appear where it
should.

#### Memories stored before this fix — remediation

What the old rules could have stored: (a) a sensitive fact the model did not
flag; (b) a fact under a category outside the prompt's vocabulary; (c) a private
note for an unknown specialist, widened into shared memory; (d) a Modeer-private
note, widened into shared memory; (e) an automatic value over a hand-saved one.

`backend/tools/memory_audit.py` finds (a) and (b). It is read-only — PostgreSQL
is put in a read-only transaction and rolled back — skips hand-saved rows, and
prints values only with `--values`. (c) and (d) look exactly like genuine shared
facts, and (e) exists only in backups taken before the overwrite, so no tool can
list them.

The process. Nothing is deleted or reclassified silently — stored memories
belong to the person they describe:

1. Take an encrypted backup first (OPERATIONS.md). It is also the only record of
   any value lost to (e).
2. Run `python -m tools.memory_audit --list` inside the backend container. Add
   `--values` only on a private terminal.
3. For each flagged account, tell the person which facts were flagged and why.
   They review them on the Memory page, where every fact can be deleted, and
   decide. An operator deletes a row only at that person's request.
4. Because (c)–(e) cannot be detected, ask every beta account to review its
   shared memories once — those are the facts every specialist now reads.
5. To recover an overwritten hand-saved value, restore a pre-overwrite backup
   into a scratch database (never over the live one), compare with `--values`,
   and give the person the old value to re-save if they want it.

Status: the dev database audit on 2026-09-11 found 0 automatic memories (file
checksum unchanged by the audit). No production deployment exists, so there is
no production data to remediate yet — run the audit once on any database that
held data before this change.

### 2. Reply completion — every reply says how it ended

Revalidated first: the provider handled a stream event's finish reason before
its content, so when the last words and the stop signal arrived together — at
exactly the end of a reply — those words were dropped. A reply cut at the token
limit was saved and shown as if whole; a stream that stopped part-way was
discarded; an empty reply was saved as "(no response)"; a blank message created
a conversation and spent provider work.

Now:

- **Provider** (`openai_compat_provider.py`, `llm/base.py`): content first, then
  finish reason. Four outcomes: completed; `truncated` (token cap — text kept);
  `interrupted` (upstream error, missing finish, timeout or connection loss
  after text — text kept); failed (nothing usable arrived, an empty reply
  included). `complete()` returns truncated text labelled, and refuses to pass
  an interrupted reply off as whole.
- **Runtime and persistence** (`agents/runtime.py`, `conversations/service.py`):
  every assistant row stores `meta.completion` and a plain-language
  `meta.notice`. A failed turn stores an empty placeholder, which is left out of
  what the model sees next time. If the person's own connection closes
  mid-reply, what arrived is saved as interrupted.
- **API** (`routes/chat.py`, `conversations/schemas.py`): `end` events carry
  `completion` and `notice`; `error` events carry `completion: failed`, the
  conversation and the saved message id. Messages read back from history expose
  `completion`, so a reload shows what the live stream showed. Blank and
  whitespace-only messages get 422 before any conversation, message or token
  charge exists (Ask My Team's question too).
- **Recovery** — `{"conversation_id": …, "retry": true}` on the same endpoint
  regenerates the latest unfinished turn **in place**: the user's message is
  reused, never written again; the unfinished reply is replaced; it is refused
  (409) once the latest reply completed; and it runs only when the person
  clicks. A retry does not re-run memory extraction for a message already
  learned from, so it costs no hidden provider call.
- **Frontend** (minimal, within the approved design): a one-line note under an
  unfinished reply; one button above the composer for the latest unfinished
  turn — *Try again* (failed, interrupted, or no reply at all) or *Continue*
  (truncated; sends "Continue from where you stopped." as a visible message).
  After a failure mid-turn the page reloads the server's record instead of
  guessing.

Tests: `test_provider_reliability.py` (final-event content, token-cap stops,
missing finish, upstream error before and after text, empty replies,
`complete()`), `test_reply_completion.py` (30: each state live and on reload,
sync endpoint, failed turns left out of the next prompt, retry for each state
without duplicates, retry refused after completion, no second extraction call,
a turn with no reply at all, the client leaving mid-reply before and after text,
and blank-message refusal with a positive control).

### 3. Remaining readiness items

- **Dependency lock.** `backend/requirements.lock` (32 packages with hashes,
  resolved on the image's platform, constrained to the tested venv); the
  Dockerfile installs it with `--require-hashes --no-deps` and runs `pip check`;
  base image pinned by digest; `test_dependency_lock.py` guards drift. See
  DEPLOYMENT.md, "Backend dependency lock".
- **Ask My Team** is off unless `TEAM_ENABLED=true` (404 for signed-in callers,
  401 still first for anonymous ones). Implementation and its tests kept; the
  suite runs with it on, and `test_release_config.py` pins the shipped default.
- **Readiness**: a single provider failure is counted and visible but no longer
  degrades readiness; three in a row for one model do. Per-minute 429s are not
  failures. Daily-quota blocks, database and schema checks, and the quota alert
  are unchanged. See OPERATIONS.md.
- **CSP** in `deploy/Caddyfile`, validated in Chrome against the production
  images (below). Rationale for the two `'unsafe-inline'` entries in
  DEPLOYMENT.md.
- **Markdown links** (`frontend/src/lib/links.ts`): http(s), mailto, `/path` and
  `#fragment` only. Protocol-relative `//host`, backslashes (`/\host`),
  whitespace and control characters, every other scheme, and bare relative
  paths are refused and render as plain words. `frontend/tools/links-check.cjs`
  checks 8 allowed and 21 refused forms plus the renderer.
- **API docs** are disabled in the app when `ENVIRONMENT=production`.
- **Docs**: counts updated here, in HANDOFF.md and DEPLOYMENT.md; earlier
  numbers kept and labelled as historical.

### Frontend files touched

Only the completion/recovery states and link handling; no layout, artwork or
styling change beyond the note and the one button, which reuse existing classes.

- `frontend/src/types/index.ts` — `Completion`, `Message.completion`,
  `meta.notice`, stream event fields.
- `frontend/src/features/chat/useChatStream.ts` — retry request; passes
  completion and notice on; reports whether the server started the turn.
- `frontend/src/components/chat/ChatWorkspace.tsx` — reloads the server's
  record after a failure mid-turn; the Try again / Continue button; marks
  optimistic messages as local.
- `frontend/src/components/chat/MessageBubble.tsx` — the one-line note under an
  unfinished reply; no "Personalised" link on a failed placeholder.
- `frontend/src/lib/markdown.tsx` — uses the link policy; refused links render
  as text.
- `frontend/src/lib/links.ts` (new) — the link policy.
- `frontend/tools/links-check.cjs` (new) — its check.

Touched again in the 2026-09-12 remediation, same scope:

- `frontend/src/components/chat/ChatWorkspace.tsx` — a visually hidden polite
  live region announcing an unfinished reply; nothing else moved.
- `frontend/Dockerfile` — base image pinned by digest (no application change).

### Release verification — evidence

| Check | Result |
|---|---|
| Backend suite (Windows dev venv) | **263 passed** |
| Backend suite inside the production image, installed set == lock | **263 passed**; image holds exactly the 32 locked packages plus pip (`deploy/tests/image-check.sh`) |
| Ruff | `ruff check .` clean; every file created or touched in this pass is format-clean except files already unformatted at `172f857`, which were not reformatted |
| Frontend | `npm run lint`, `npm run typecheck` clean; production build succeeded in the frontend image; `node tools/links-check.cjs` passed |
| Production rehearsal (`deploy/tests/production-rehearsal`) | **16/16** in Chrome, 0 CSP violations, 0 page errors — `docs/production-rehearsal-results.json` |
| API docs in the production image | `/docs`, `/redoc`, `/openapi.json` → 404 |
| Readiness in the production image | 200, `environment: production`, `schema_current: true` on PostgreSQL 16 after `alembic upgrade head` |
| Memory audit, dev database | 0 automatic memories; database unchanged |
| Agent quality, release configuration | **Incomplete**: 27/39 cases before the daily quota; 21 passed, 2 failed, 4 ungraded — below |

The rehearsal covered onboarding → chat → memory → follow-up, streaming through
Caddy, all four completion states and their recovery, the browser going offline
mid-reply and coming back, blank messages, conversation deletion, account
switching, readiness through the proxy, and a 390px layout. Its model was
scripted, its TLS certificate came from Caddy's local CA, and its browser was
desktop Chrome at phone width: it is not evidence about a real domain, a phone,
a cellular network or the real model.

Exact commands:

```sh
cd backend
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m tools.memory_audit --list
.venv/Scripts/python.exe -m tools.provider_doctor
.venv/Scripts/python.exe quality_check.py --samples 3 --judge-model qwen/qwen3.8-27b \
  --out ../docs/quality-launch-verified.json --resume
cd ../frontend && npm run lint && npm run typecheck && node tools/links-check.cjs
# from the repository root:
docker build -t modeer-backend:check backend
docker run --rm -v "$PWD/backend/tests:/app/tests:ro" \
  -v "$PWD/deploy/tests/image-check.sh:/image-check.sh:ro" modeer-backend:check sh /image-check.sh
# production rehearsal: deploy/tests/production-rehearsal/README.md
```

### Configuration required for release

`ENVIRONMENT=production`, `DEBUG=false`, `AUTH_REQUIRED=true` (compose sets
these); an `https://` `FRONTEND_URL`; a strong `AUTH_SECRET`; `AUTH_ACCESS_KEYS`
provisioned per DEPLOYMENT.md; `TEAM_ENABLED` unset or `false`;
`MEMORY_STORE_SENSITIVE` unset or `false`; at least one alert channel; images
built from this tree (the lock and pinned base come with it).

### Agent quality, release configuration — INCOMPLETE (quota)

The established launch run was resumed on the exact release settings — Groq,
`openai/gpt-oss-120b` for every agent except Writing's own `qwen/qwen3.8-27b`,
reasoning effort `low`, prompt versions unchanged since its first rows — graded
by `qwen/qwen3.8-27b`, three samples of the thirteen cases. No model or setting
was changed.

```sh
cd backend
.venv/Scripts/python.exe quality_check.py --samples 3 --judge-model qwen/qwen3.8-27b \
  --out ../docs/quality-launch-verified.json --resume
```

It **did not finish**: after 27 of 39 cases the provider asked for a 479-second
wait — the daily quota — and the harness stopped as designed, keeping
`docs/quality-launch-verified.json.partial`. The same command resumes it on a
fresh budget. Gate 1 stays open until it completes.

What the 27 show (samples 1 and 2 complete, sample 3 one case):

| | Result |
|---|---|
| Passed / failed / ungraded | **21 / 2 / 4** — the four ungraded are the rows from earlier today whose grading hit that day's quota; ungraded is never a pass |
| Deterministic rubric (length ceilings, forbidden phrases, stale-price and capability claims) | 27/27 — no `too_long`, previously the dominant failure (11 of 14) |
| Provider errors / truncated at the token cap | 0 / 0 (truncation is recorded per row from this pass on) |
| Latency, provider completion in the harness | 0.53–3.14 s, median 1.47 s — not browser end-to-end, not under load |
| Length | 5–437 words |

The two failures, both flagged by the judge with quoted evidence:

- **Writing, sample 1** (`delivers`): the bio left a literal
  `[placeholder for specific focus or research …]` in the text. A real defect.
  Writing is graded by its own model, so this grade is not independent evidence
  either way.
- **Career, sample 2** (`concision`): the judge objected to padding around the
  trade-off. Read the stored answer before acting; the judge produces false
  positives.

Judge dimensions: grounding (no invented personal facts — the unsupported-claims
check), delivers (completeness, no placeholders), currency, respects
preferences (personalization), capability honesty, concision (verbosity).
Specialist distinction is covered only indirectly, by per-specialist fixtures
and scope checks; nothing in the harness compares one specialist's answer with
another's.

Not comparable yet with the 25/39 baseline: twelve cases are missing and four
are ungraded. 21 of 23 graded rows passed.

## Review remediation — 2026-09-12

Every code finding from `production-readiness-review-2026-09-11.md` is fixed,
with a regression test each (`backend/tests/test_review_fixes.py`, plus three
new checks in the production rehearsal). Dispositions for all of them are listed
at the end of the review document.

**Fixed**

- **Memory-page corrections are the person's.** A `PATCH` now records the fact
  as theirs, so automatic extraction leaves it alone — the protection already in
  place for hand-saved facts. `app/memory/service.py`.
- **A duplicate label is answered, not crashed.** Renaming a fact onto an
  existing label returns 409 with a readable message; it no longer raises a 500
  that counted as an unhandled error, degraded readiness and paged the operator.
  Keys and values are validated and bounded (2000 characters), and the memory
  block in a prompt has a 6000-character ceiling.
- **An unfinished reply is announced.** The chat page carries a polite live
  region, so a failed, truncated or interrupted reply reaches a screen reader
  instead of only being drawn. This was a regression from the previous pass.
- **A revoked or deleted session gets 401 from the chat stream.** The account is
  resolved before the response starts, so the client's existing redirect to the
  login page fires instead of "the reply was interrupted".
- **Overlapping retries cannot answer twice.** Turns in one conversation are
  serialised in the process; a second retry that arrives mid-stream then finds
  the reply finished and is refused with 409.
- **Memory trouble after a finished reply** is reported as a memory problem, not
  as a failed reply.
- **Timeouts say which one fired:** a provider that goes quiet mid-stream reads
  "stopped responding"; a reply still arriving when the total cap is reached
  reads "ran past the time limit".
- **Production refuses the mock model** and a missing `LLM_API_KEY`.
- **Message order no longer depends on a clock tick.** Messages are ordered by
  time, and a clock need not advance between two writes (Windows moves in ~15ms
  steps), so a reply could sort before the question it answered — in the
  transcript, in what the model was sent, and in what a retry considered "last".
  `add_message` now assigns a strictly increasing time per conversation. Found
  while fixing the above; it was latent, not introduced by it.
- **The rules extractor** no longer keeps trailing words ("Alexandria now").
- **Images are pinned by digest** for the frontend, database and proxy too.
- **Documentation corrected:** the privacy notice now says what actually leaves
  the server (conversation history and the separate extraction request), that
  sensitive-fact detection is best effort, and that an edit of yours stands;
  `product.md` records that Ask My Team ships off.

**Then found by re-checking that work** (a second pass over the same day's
changes, before deployment):

- **The idle timeout was also capping the wait for the first token.** Splitting
  one 35-second budget into "idle" and "total" left the first token with 15
  seconds, so a reply the provider had merely queued would have failed with
  "took too long". The idle window now starts counting only once words are
  flowing. Reproduced (a 1-second first token failed; it now streams) and
  pinned by a test.
- **Pinning a fact froze it.** Recording a hand edit as the person's own was
  applied to any `PATCH`, so pinning a fact — "keep this in view" — also stopped
  automatic updates. Only edits to what a fact *says* (key, value, category)
  count as the person's words now; the pin survives a later update.
- **Access logs lost the `/api` prefix.** FastAPI 0.141 keeps included routers
  nested, so the logged route template read `/agents/{agent_id}/chat`. The
  template is rebuilt from the request path with each id replaced by its
  parameter name — and if any id would survive that, the relative pattern is
  logged instead, because an id must never reach a log.

**Dependencies upgraded.** A Python audit (`pip-audit`, run in a container
against the lock) reported 14 advisories against Starlette 0.46.2, which
FastAPI 0.115 pins. Upgraded to **FastAPI 0.141.1 / Starlette 1.6.0**; the lock
was regenerated and the audit now reports none. FastAPI 0.141 no longer flattens
included routers into `app.routes`, which silently reduced the authentication
sweep in `tests/test_auth.py` to zero routes — it now reads the generated schema
instead, so it cannot quietly check nothing again. The frontend's own advisory
(`next` → `postcss`) still needs a major Next upgrade and is the owner's call.

**Evidence (2026-09-12)**

| Check | Result |
|---|---|
| Backend suite | **283 passed** (263 before, plus 20 regressions), Ruff clean |
| Backend suite inside the production image | **283 passed**; image holds exactly the 33 locked packages |
| `pip-audit` against `requirements.lock` | **No known vulnerabilities** (was 14) |
| Production rehearsal, Chrome | **19/19**, zero CSP violations, zero page errors; access logs name the full route with no ids |
| Live journey on the real model (`journey_check.py`) | **12 of 13 steps**; every application step passed. The one failure is the model's answer, not the app: see the quality note below |
| Agent quality, release configuration, complete run | **12/13** — `docs/quality-release-2026-09-12.json` |
| Frontend lint, typecheck, link policy | Clean |

**Agent quality, 2026-09-12 (complete, single sample of 13 cases).** Groq,
`openai/gpt-oss-120b` for every agent except Writing's `qwen/qwen3.8-27b`,
reasoning `low`, judge `qwen/qwen3.8-27b`, code revision recorded in the results
file. 12 passed, 1 failed, none ungraded, no provider errors, nothing truncated,
0.56–3.2s per reply, 9–444 words.

The one failure is real and worth fixing: asked for a two-week study plan from a
context saying "thermodynamics final on the 20th", Study wrote "final on 20 May"
— inventing the month. The deterministic rubric catches this class
(`invented_month`), so a prompt change can be measured. It is left for a
decision rather than changed hours before a deployment: the rule lives in the
shared guardrails, so editing it invalidates the other twelve results and needs
a full re-run.

**A second measured answer-quality defect, from the live journey.** Asked "What
should I revise first?" with the exam and subject already in its prompt, Study
replied with a clarifying question alone — "before we pick a starting point,
let's see where your confidence is strongest" — and named none of the stored
facts. The diagnostic beside it confirms the facts *were* in the prompt
(`context_used` true), and the prompt's rule 2 forbids exactly this ("Never
answer with questions alone"), so it is the model disregarding an instruction.

### Both were addressed the same day

Two rules in the shared block (`app/agents/context.py`) were tightened, and every
agent's `prompt_version` was bumped, since the block belongs to all of them:

- **Rule 2** now says to open with the answer and never with a question: a short
  or vague ask is still an ask, answered from what is already known, with the
  reading named in a clause; any question comes last, after something usable.
- **Rule 3** now says a date or place stays exactly as given — "the 20th" is
  "the 20th", never "20 May", and never a year that was not given.

**Measured before and after, on the live model** (`openai/gpt-oss-120b`, release
settings). A targeted probe ran each failing case four times and graded it with
the deterministic rubric:

| Case | Before | After |
|---|---|---|
| "What should I revise first?" — answers rather than interviews | 1 of 4 failed (plus 2 of 3 in the journey) | **0 of 4** |
| Two-week plan — invents a month from "the 20th" | 1 of 13 in the suite, 0 of 4 in the probe | **0 of 4**, and 0 of 13 in the suite |
| Full 13-case suite | 12/13 (`quality-release-2026-09-12.json`) | 12/13 (`quality-release-2026-09-12b.json`) |

The suite's score is unchanged but its failure moved: the invented month is gone;
what failed instead was Research at 462 words against a 450-word ceiling — 12
words over, and total words across the thirteen replies *fell* (2170 → 2067), so
the longer rules did not inflate answers. On single samples that is variance, not
a regression.

**One check was wrong, not one reply.** The journey's recall test searched for
the words "thermodynamic", "mechanical" or "engineering". After the fix it failed
a reply that opened "Start with the fundamental laws — especially the First and
Second Laws" — a good, grounded answer that never uses the subject's name. That
is keyword scoring, the thing this repository already decided against, so the
check was made precise instead of relaxed: it now asserts deterministically that
the specialist answers rather than interviews, and reports the keyword hits as an
observation.

**What this evidence is worth.** Four samples per case and one suite run each
side. It shows the defects did not recur; it does not prove they are rare. A
three-sample suite run on fresh quota is the next measurement.

One more observation from the live journey: the in-process test client does not
deliver a disconnect, so what a real server does with a dropped connection is
proven in the rehearsal, not there. The journey's wording was corrected to say
so — it had claimed the reply was "abandoned without a stored reply" while
asserting nothing of the kind.

## Owner decisions implemented — 2026-09-13

The review-remediation work above was committed as `ee5328d`. The owner then
asked for the open items and product decisions to be done, choosing **open
signup**, **password** sign-in, **recovery codes**, and automatic memory **on,
with a per-person switch**. Everything below is on top of `ee5328d`.

**Accounts**

- **Open signup behind a switch.** `SIGNUP_ENABLED` (default `false`) adds
  `/signup`: name, email, password (10–128 characters). Passwords are hashed with
  scrypt (`app/core/passwords.py`). Signup issues ten single-use recovery codes,
  shown once, stored as SHA-256 hashes; the page will not continue until the
  person ticks "I've saved these codes". `AUTH_ACCESS_KEYS` is no longer required
  to start; invitation keys keep working beside passwords.
- **Password sign-in** answers a wrong password and an unknown email with the
  same message after the same work (a decoy hash is checked when there is no
  account).
- **Recovery.** `/recover` takes email, code and a new password; the code is
  spent, every other session ends, and the page says how many codes are left.
  The Account page changes the password (other sessions end), sets a first
  password on a key account (which issues codes), and makes a fresh set of codes
  (old ones retired). A wrong confirmation password answers 403, not 401, so the
  page is not sent to sign in mid-form.
- **Last resort for the operator:** `provision_user.py --rotate --clear-password`
  for someone who has lost the password and every code (OPERATIONS.md).
- **Throttles:** 10 password or recovery attempts per email per 15 minutes; 5
  signups per client address per hour. Counters live in `usage_buckets` under
  hashed subjects.
- **Schema 0004:** `users.password_hash`, `users.memory_auto`, `recovery_codes`.
  Email changes are refused for password accounts (the email is the sign-in
  name); profile fields are bounded.

**Privacy and consent**

- **Automatic memory has a per-person switch** (Account → What Modeer learns).
  Off means no extraction call is made at all; saving by hand still works and
  nothing stored is removed. It is in the export.
- **Ask My Team no longer carries private notes.** A consult builds each
  specialist's prompt from shared context only and learns nothing, so a
  specialist's private notes cannot reach Modeer through its answer. Proven at
  the provider's input, with a positive control that an ordinary chat does
  include them.
- **Failed calls are refunded.** A provider failure before any text returns the
  charge to the account's window; anything that produced text stays charged.
  `docs/usage-limits.md` records the caveat that the provider may still have
  counted it.

**Public surface**

- `/api/health` answers `status` and `database` only in production;
  `/api/health/detail` answers `status`, `database`, `schema_current` to anyone
  and the full body only to signed-in `ADMIN_ACCOUNTS`. `watchdog.sh` reads only
  `status`.
- `/api/agents/{id}` no longer shows model settings or the prompt framework.
- The synchronous chat route answers 404 in production.

**Frontend (owner-authorised for these items)**

- **Next 16.3.5** (`eslint-config-next` 16.3.5; ESLint flat config). `npm audit
  --omit=dev`: 0 vulnerabilities. Next 16's new React Compiler lint rules flag
  five existing patterns; they are set to *warn*, not refactored, so the owner's
  components are unchanged (0 errors, 13 warnings).
- **Nonce CSP.** `src/proxy.ts` sends a per-request policy with `'nonce-…'
  'strict-dynamic'` and no `'unsafe-inline'` for scripts; pages render per
  request (`await connection()` in the root layout). Styles keep
  `'unsafe-inline'` for `style=""` attributes. Caddy keeps a nonce-less fallback
  for responses without a policy, plus COOP and `Permissions-Policy`;
  `X-Powered-By` is off.
- **Validation errors are readable.** `apiFetch` turned FastAPI's list of field
  errors into "[object Object]"; it now shows the sentences. Found by the
  rehearsal.

Frontend files touched, all new UI using the existing classes and colours:
`package.json`, `package-lock.json`, `tsconfig.json` (Next's build set
`jsx: react-jsx`), `.eslintrc.json` (removed), `eslint.config.mjs` (new),
`next.config.mjs`, `src/proxy.ts` (new), `src/app/layout.tsx`,
`src/app/login/page.tsx`, `src/app/signup/page.tsx` (new),
`src/app/recover/page.tsx` (new), `src/app/account/page.tsx`,
`src/components/auth/RecoveryCodes.tsx` (new), `src/components/AppShell.tsx`,
`src/lib/api.ts`, `src/types/index.ts`, and
`src/components/goals/GoalsManager.tsx` (one attribute, below).

**Accessibility**

`deploy/tests/production-rehearsal/accessibility-check.cjs` ran axe-core (WCAG
2.2 A/AA and best practice) on eleven pages plus the recovery-code screen, at
1280px and 390px, and a keyboard-only pass (`docs/accessibility-results.json`):

- **Keyboard:** every page reachable by Tab, every stop on screen with a visible
  focus indicator; signup through to a first message works without a mouse.
- **Names, roles, labels, landmarks, headings:** no violations. The one item
  axe flagged for review — an `aria-label` on a plain `div` in the Goals summary,
  which screen readers ignore — now has `role="group"`. Invisible change.
- **Colour contrast — not changed, owner's call.** White text on the pink
  buttons (`#ffffff` on `#ff438a`) is **3.27:1**, below the 4.5:1 AA minimum for
  14px bold text; it appears on Login, Signup, Recover and two Account buttons.
  One pink link on Team (`#e6296f` on `#fffcf2`) is **4.16:1**. Darker pink,
  dark text on pink, or larger button text (18.66px bold counts as large, 3:1)
  would each pass.
- **Not done:** a pass with a real screen reader (NVDA or VoiceOver). Automated
  scans catch perhaps a third of real problems; this is evidence, not sign-off.

**Three-sample quality run — partial.** `docs/quality-release-2026-09-13.json.partial`,
recorded at `ee5328d` (release settings: `openai/gpt-oss-120b`, Writing on
`qwen/qwen3.8-27b`, reasoning `low`, judge `qwen/qwen3.8-27b`). The daily quota
stopped it at **36 of 39** cases: **32 passed, 4 failed**, deterministic rubric
36/36, no provider errors, nothing truncated. All four failures are the judge's
grounding and concision checks:

| Case | Judge's complaint | Adjudication |
|---|---|---|
| Modeer, sample 1 | concision: a "Day-by-day plan" heading | Likely judge false positive; the plan was asked for |
| Study, sample 1 | grounding: "have roughly 2 h / day" | Contested: stated as an assumption, not as a fact about the person |
| Fitness, sample 1 | grounding: "dumbbells (up to ~20 kg)" | **Real** — an invented detail |
| Shopping, sample 2 | grounding: compact phone; also "typically £429–£479" | **Real** — an unsupported price claim the rubric does not catch |

The two defects fixed on 2026-09-12 (invented month, question-only answer) did
not recur in 36 cases. Two real grounding lapses remain at roughly one in
eighteen replies; no prompt change was made for them in this pass. The last
three cases were not run: the code has changed since, so finishing needs
`--resume --allow-code-change` (mixing revisions, recorded as such) or a fresh
run on a new day's quota.

**Evidence (2026-09-13)**

| Check | Result |
|---|---|
| Backend suite | **314 passed** (283 + 31), Ruff clean, new and touched files formatted |
| Backend suite inside the production image | **314 passed**; image holds exactly the locked set |
| `alembic upgrade head` + `alembic check` | Head 0004, no drift; downgrade and re-upgrade clean |
| Production rehearsal, Chrome | **23/23** checks, zero CSP violations, zero page errors — `docs/production-rehearsal-results.json` |
| Accessibility check | No violations except colour contrast: 7 elements on 6 pages, at both widths; keyboard pass clean |
| Frontend | typecheck clean; lint 0 errors (13 warnings); production build; link policy 8 allowed / 21 refused |
| `npm audit --omit=dev` | **0 vulnerabilities** (was the `postcss` advisory) |
| Backend lock | unchanged since `ee5328d` (audit clean then) |

## Remaining launch gates

Production readiness is **not** claimed. Status after the 2026-09-13 pass:

1. **Answer quality — two grounding lapses remain.** The three-sample run
   (partial, 32/36) found an invented equipment detail and an unsupported price;
   the rubric does not catch prices. Decide whether to tighten grounding for
   Fitness and Shopping, then finish or re-run the three-sample suite on fresh
   quota. Free-provider quotas remain shared across all users and can stop
   replies even when the app works correctly.
2. **Real host and domain — not verified (owner).** TLS from a public CA, secure
   cookies, cross-account denial, streaming and interrupted reconnection on the
   real domain. The local rehearsal covered the same checks with Caddy's local
   CA; it does not replace this.
3. **Off-host backup restore — not verified (owner).** Install the scheduler,
   confirm the destination is genuinely remote, verify its retention/version
   rules, and restore from that storage.
4. **Operator delivery — not verified (owner).** Configure a real recipient and
   confirm receipt of outage, recovery, backup-failure and test notifications.
5. **Physical phone and a screen reader — not verified.** The 390px checks ran
   in desktop Chrome. The automated accessibility scan and keyboard pass are
   done; a pass with NVDA or VoiceOver is not.
6. **Colour contrast (owner).** Pink buttons at 3.27:1 and one Team link at
   4.16:1 fail WCAG AA; see Accessibility above. A design decision.
7. **Memory remediation** — run `tools.memory_audit` on any database that held
   data before this change, and follow the process above.
8. **Backup round-trip on schema 0004** — rerun once; the last one was on 0003.

The account model is now the operator's choice: invitation keys only
(`SIGNUP_ENABLED=false`, the default) or open signup with passwords and recovery
codes. There is no email-based reset by design.
