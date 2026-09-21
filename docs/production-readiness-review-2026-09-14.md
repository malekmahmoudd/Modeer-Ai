# Independent application review — 2026-09-14

**Subsequent update:** the owner authorized fixes after this read-only review.
R14-01–04 are now implemented and regression-verified; see the remediation
appendix at the end. The original review below remains the historical record.

## Decision and scope

**Local use: usable with known defects. Invite-only beta: conditional hold.
Public production: hold.** Three functional defects and one inaccurate privacy
statement remain below. No new high-severity exploit was reproduced.

This is the read-only review requested in the latest edited handoff instructions.
It supersedes the earlier instruction to fix findings during this pass. No
application code, frontend design, deployment or existing evidence was changed.
Only this report was added. Tests used temporary databases, synthetic accounts,
mock/scripted responses and localhost services. No live AI generation or response
quality evaluation was performed.

Reviewed HEAD: `1ed17eb5748d948a541f0e76a7fabcddd094534d`, **plus the existing
remediation working tree**, not the commit alone. Pre-existing modifications:
backend context, auth/users routes, goal schemas, profile service, quality runner;
frontend workspace, stream hook and event types; deployment/launch/accessibility
documentation. Pre-existing untracked files included the September 13 regression
tests, stream check, project/mobile reports, independent review, quality ledger,
complete remediation quality result and older partial result. They were preserved.

Read the [September 13 review and remediation appendix](production-readiness-review-2026-09-13.md),
the [earlier review](production-readiness-review-2026-09-11.md),
[handoff](HANDOFF.md), [launch notes](launch-fixes.md), and implementation.
This review is broad source inspection plus targeted checks, not proof that every
possible interleaving, browser, deployment or failure has been exercised.

## Prioritized confirmed findings

### R14-01 — Medium: older fetches can overwrite newer shared-memory state

**New finding; reproduced in installed Chrome against the production frontend
build and a real localhost API.** Relevant source:
[api.ts:63](../frontend/src/lib/api.ts#L63), especially line 75;
[MemoryManager.tsx:184](../frontend/src/components/memory/MemoryManager.tsx#L184)
and the add handler at line 204.

`useApi` checks only whether the component is mounted before applying a result.
It does not check which request is newest. Memory mutation handlers trigger a
refetch without awaiting its completion before allowing the next edit.

Reproduction with synthetic facts:

1. Sign in and open Memory, allowing its initial request to finish.
2. Add `review_first = REVIEW FIRST FACT`. Intercept the ensuing GET
   `/api/memory/shared`, fetch its actual response, but hold delivery to the page.
3. Add `review_second = REVIEW SECOND FACT`. Let this mutation and its newer GET
   complete. The second fact appears.
4. Release the held first GET. The second fact disappears from the rendered list.
5. Read `/api/memory/shared` again: the second fact is still stored.

Observed browser probe: `secondFactVisible: 0, stored: true`. There were no page
errors in this probe. Expected: a stale request cannot replace more recent state.
Actual: a successful save appears lost. This is a same-account UI consistency
defect; no database deletion or cross-account disclosure was demonstrated.

**Correction:** give `useApi` a monotonically increasing request identity, discard
stale completions/errors/finalizers, invalidate requests on path changes/unmount,
and consider cancellation. Test reversed response order after consecutive saves
and overlapping refetches. Other consumers share the hook, but this report does
not claim every consumer was separately reproduced. Specialist private-note
loading already has its own request guard at
[MemoryManager.tsx:118](../frontend/src/components/memory/MemoryManager.tsx#L118);
the reproduced defect is the shared list, not that guarded path.

**Release impact:** fix before beta so saved facts are represented reliably.
No visual redesign is needed.

### R14-02 — Medium: explicit null updates escape request validation

**New finding; reproduced through real FastAPI routes on an isolated SQLite
database.** Sources:
[ProfileUpdate:13](../backend/app/users/schemas.py#L13),
[GoalUpdate:15](../backend/app/goals/schemas.py#L15),
[goal update service:35](../backend/app/goals/service.py#L35),
[SharedMemoryUpdate:38](../backend/app/memory/schemas.py#L38),
[user exception mapping:38](../backend/app/api/routes/users.py#L38),
[memory exception mapping:48](../backend/app/api/routes/memory.py#L48).

The PATCH models use nullable types to represent omitted fields. Explicit JSON
null is also accepted, then `model_dump(exclude_unset=True)` includes it. Services
write it into required fields, or response validation fails. Broad integrity-error
handlers additionally mislabel these failures as email or memory-label collisions.

Fresh HTTP probe results, one null field per request:

- Create a valid goal, then PATCH its `title`, `detail`, `priority` or `status`
  to null: **500** for each.
- PATCH `/api/users/me` with `profile: null`: **500**.
- PATCH `display_name`, `onboarded` or `memory_auto` to null: **409**, mapped to
  the email-already-used message rather than field validation.
- Create a shared memory, then PATCH `value`, `key`, `category`, `confidence`,
  `sensitive` or `pinned` to null: **409**, mapped to the duplicate-label message.

Expected: **422** for explicit null in a non-nullable field. Omitted fields should
remain unchanged; genuinely nullable fields such as a goal's target date must
retain their deliberate clear operation. Actual: normal malformed requests become
server failures or misleading conflicts. The inspected synthetic database retained
its original profile after rollback; permanent account corruption was not observed.

**Correction:** distinguish omission from explicit null in update validation;
reject null for required stored fields before applying the patch. Preserve
intentional nullable operations. Narrow conflict translation to known unique-key
violations. Add route tests for every update field and assert both response code
and unchanged stored state on rejection. Agent-memory schemas have the analogous
pattern, but their null matrix was not independently exercised in this probe.

**Release impact:** fix before beta. These endpoints should not generate 5xx
responses from routine invalid input; such errors also enter operational error
accounting. This is not an unauthenticated access bypass.

### R14-03 — Medium: failed new-conversation creation has no usable error state

**New finding; reproduced in Chrome with a deliberately failed request.**
[ChatWorkspace.tsx:201](../frontend/src/components/chat/ChatWorkspace.tsx#L201),
button consumers at lines 290 and 432.

`newConversation()` awaits POST `/api/conversations` without handling rejection.
React's event handler does not turn that rejected promise into the existing error
notice. Reproduce by opening a specialist, intercepting that POST with a network
abort, and clicking **Start a new conversation**.

Expected: retain the current view and show/announce a useful failure with a retry
path. Actual: captured uncaught page error **`Failed to fetch`**, no useful visible
alert (`visibleAlerts: [""]`). The action appears to do nothing. The injected
network fault is intentional; the application's unhandled rejection is the defect.

**Correction:** handle this mutation's loading and error states, preserve the
current conversation on failure, and use the existing notice/announcement area.
Exercise network failure and a returned API error in browser tests. Review repeated
clicks as part of that implementation; duplicate creation was not separately proven.

**Release impact:** fix before beta. This requires behavior changes, not a design change.

### R14-04 — Low: Memory still promises perfect sensitive-data filtering

**Unresolved documentation/UI inconsistency; confirmed by source comparison.**
[MemoryManager.tsx:146](../frontend/src/components/memory/MemoryManager.tsx#L146)
says Modeer “never saves sensitive details … on its own.”
[sensitivity.py](../backend/app/memory/sensitivity.py) explicitly states its keyword
backstop can miss sensitive facts, and the [privacy notice](../backend/app/legal/privacy.md)
describes best-effort detection. The deployment reference was corrected in the
previous pass, but the visible statement remains absolute.

Expected: the Memory screen accurately describes the filtering limitation and
automatic-memory control. Actual: it promises a stronger guarantee than the code
or privacy notice supports. No new live extraction or sensitive-data leak was
tested in this pass.

**Correction:** replace the absolute promise with accurate plain language about
attempted filtering and the user's review/switch controls. Keep the existing layout.
**Release impact:** reconcile before external onboarding; this is a disclosure
defect, not a newly demonstrated authorization vulnerability.

## Fresh verification and exact limits

Host: Windows, Python **3.12.10**, Node **24.14.1**. Frontend build: Next **16.3.5**.
The production Dockerfile uses pinned Node 22, so the local build is not a fresh
test of that image/runtime. Temporary audit/browser tooling was installed outside
the repository; project dependencies were not changed.

- Full backend suite: **326 passed**, one Starlette TestClient deprecation warning,
  28.13 seconds. Ruff passed. `pip check` found no broken installed requirements.
- Frontend lint: **0 errors / 13 existing warnings**. Typecheck and production
  build passed. Warnings include hook/effect patterns and full-page navigation;
  they are not all proven runtime defects. Do not replace account-change reloads
  mechanically with client navigation without considering state isolation.
- Link policy/renderer: **8 allowed / 21 refused** cases passed. Stream-hook check:
  completed answer retained and separate memory failure delivered.
- Fresh `npm audit --omit=dev`: **0 reported vulnerabilities**.
- Fresh isolated `pip-audit --disable-pip --no-deps -r requirements.lock -f json`:
  **0 known vulnerabilities across 33 locked packages**. This queried the locked
  versions; it did not rebuild a Linux image or prove absence of unknown flaws.
- Alembic, empty temporary SQLite database: upgrade to head, downgrade to `0003`,
  re-upgrade to head all passed. Final revision **0004**, **10 application tables**
  plus Alembic metadata. This was not a data-bearing PostgreSQL rollback or restore.
- Installed Chrome, production frontend at `http://localhost:3300`, disposable
  authenticated API at `http://127.0.0.1:8102`: invitation login, password signup,
  ten recovery codes, acknowledgement gate, onboarding, automatic-memory switch
  and password recovery passed. Onboarding completed after three synthetic facts
  were stored; a one/two-fact message did not yet meet its documented threshold.
- Seven signed-in routes at **1440 and 390px**: Home, Team, Memory, Goals, Account,
  Privacy, Study workspace; **14 scans, no horizontal overflow or uncaught page
  errors** in that navigation scan. Separate intentional fault tests are above.
- **20 axe-core 4.13.0 scans, zero violations**: those seven routes plus Login,
  Signup and Recover at both widths, WCAG 2 A/AA, 2.1 AA, 2.2 AA and best-practice
  tags. This does not certify screen-reader usability or physical-phone behavior.
- Page CSP nonce changed between requests. No new Caddy/TLS/header-stack rehearsal
  was possible. The HTTP test session did not verify production Secure-cookie flags.
- Scripted `end(completed)` followed by `memory(error)` rendered a completed answer
  and visible failure notice in the real browser: fresh verification of R13-02.

The browser API bridge used Playwright `route.fetch` to the real temporary backend.
It can buffer bodies: **do not interpret these browser checks as incremental
streaming or proxy-disconnect evidence**. Runtime/transport unit regressions passed,
including completion, cancellation, retries, budgets and provider error handling.
The real TLS/Caddy/offline streaming rehearsal remains a separate gate.

Reproduce main checks from their respective directories:

```text
backend:  .venv/Scripts/python.exe -m pytest -q
backend:  .venv/Scripts/python.exe -m ruff check .
backend:  .venv/Scripts/python.exe -m pip check
frontend: npm run lint
frontend: npm run typecheck
frontend: npm run build
frontend: node tools/links-check.cjs
frontend: node tools/stream-check.cjs
frontend: npm audit --omit=dev
```

Use a temporary database and `LLM_PROVIDER=mock`, `MEMORY_EXTRACTION=rules`,
disabled real alert channels for API probes. Never reuse production credentials
or run destructive fixture setup against a real database. The broader isolated
production procedure is in the [rehearsal README](../deploy/tests/production-rehearsal/README.md).
Temporary browser scripts used for this review were outside the repository; the
findings above describe their interception order and assertions for reproduction.

## Mechanisms inspected and previous-finding dispositions

Authentication uses signed, epoch-bound cookies, account-scoped route dependencies
and origin checks. Runtime quotas are database-backed; conversation serialization
and operational counters remain process-local. Keep the documented single-worker
topology. Shared/private filtering is enforced before prompt construction;
[provider-input tests](../backend/tests/test_prompt_isolation.py) inspect actual
captured system/messages with positive controls and passed. These use recording
providers, not judgments of generated answers.

Exports/deletion, user-authored memory protection, extraction validation and opt-out,
goal operations, readiness, admin access, alerts, provider timeout/refund behavior,
completion states and retry persistence are covered by the passing backend suite.
Source inspection also covered production Dockerfiles, Caddy, migration startup,
backup encryption/copy/retention, restoration and watchdog scripts. Inspection
alone does not establish that those jobs are installed or operators receive alerts.

The latest findings and all earlier identifiers carried forward by the September 13
review are dispositioned below. “Implemented/tested” means the scoped local evidence
above, not production certification.

| Prior item | Current disposition |
|---|---|
| R13-01 recovery-code reuse | Implemented; same-code and distinct-code concurrent SQLite regressions pass, including cookie epochs. PostgreSQL credential races remain unverified. |
| R13-02 / RR-06 post-answer memory failure | Implemented; hook regression and new browser notice/answer-preservation check pass. |
| R13-03 / RR-09 aggregate context | Merged profile validation, goal bounds and per-block legacy clipping implemented; regressions pass. R14-02 is a separate explicit-null issue. |
| R13-04 / RR-12 / CG-4 evidence | New source/settings/per-row fingerprints and resume checks implemented. Complete quality artifact exists. Visible privacy wording remains R14-04. |
| Initial scope promotion / missing sensitivity flags | Invalid scope/malformed flags rejected conservatively; privacy tests pass. False-negative detection remains best effort. |
| Initial final-chunk loss / silent truncation | Provider/runtime regression coverage passes; persisted completion states retained. |
| Initial whitespace chat | Validator/regressions pass. |
| #1 schema readiness | Dynamic migration-head check implemented; schema tests and SQLite migrations pass. |
| #2 / RR-10 reproducibility | Hash-locked backend and pinned production base images present. Local build/audits pass; image rebuild not rerun. Rehearsal helper tags still float. |
| #3 unused Ask My Team | Default off; no web caller. Enabled/disabled behavior tested. Shared-only consults do not extract memory. |
| #4 readiness flapping | Sustained-provider-failure handling implemented/tested; database/schema and quota failures remain distinct. |
| #5 prompt isolation | Actual captured provider-input tests pass, including specialist/account separation and team shared-only context. |
| #6 CSP / PD-1 | Nonce script policy implemented; fresh nonce-rotation check passes. Inline style allowance documented; production proxy stack not rerun. |
| #7 links | Unsafe/protocol-relative/backslash link policies and renderer checks pass. |
| #8 docs / PD-5 | Production app disables interactive docs and sync chat; release-configuration tests pass. |
| #9 stale counts | Current September 13 ledger/report separate historical counts; this report adds fresh results rather than rewriting history. |
| RR-01 manual memory edits | User source protects corrections against automatic overwrite; tests pass. |
| RR-02 announcements | Source/stream browser notice verified; physical assistive-technology pass remains open. |
| RR-03 duplicate memory label | Known collision tests pass; overly broad exception mapping also mislabels null input, R14-02. |
| RR-04 revoked sessions | Account/epoch resolution before stream starts implemented/tested. |
| RR-05 retry overlap | Serialized per process and tested. No multi-worker turn claim or general idempotency guarantee. |
| RR-07 timeout wording | Idle and overall timeouts distinguished/tested; frontend's 50-second cap remains separate. |
| RR-08 production mock | Production rejects mock/missing provider key; tests pass. |
| RR-11 rule-extractor filler | Trimming/regression tests pass. |
| CG-1 / PD-4 sensitivity and consent | Default-on automatic memory with opt-out; existing/user-saved context can still reach models. Detection remains best effort; UI wording is R14-04. |
| CG-2 / OG-6 model quality | Historical complete 33/39 remediation run exists; quality acceptance remains open. No new response evaluation here. |
| CG-3 runtime journey | New synthetic browser onboarding/account journey plus unit regressions passed. No fresh live-provider or production-domain journey. |
| CG-5 advisories | Fresh Python locked-version and frontend production audits report zero known vulnerabilities. |
| CG-6 accessibility | Fresh 20-scan axe run clean; phone-width layout clean. Physical phones/screen readers remain unverified. |
| CG-7 regression evidence | 326 tests pass; R14-01–03 still need regression tests with their future fixes. |
| PD-2 public metadata | Minimal public health/agent metadata and admin-gated detail implemented/tested. |
| PD-3 refunds | Pre-text provider failures refunded; partial/cancelled work remains charged; tests pass. |
| PD-6 team behavior | Shared-only, no learning; consult conversations still enter specialist history. Disabled malformed requests may validate before returning feature-off. |
| PD-7 Continue | New user turn, not transport resume or regeneration; unchanged documented product choice. |
| PD-8 headers | Header controls present in proxy/framework source; real deployment verification remains open. |
| OG-1–5 operational gates | Real domain/host, remote restore and scheduling, operator delivery, physical-device/assistive checks and applicable stored-data remediation remain open as detailed below. |

## Quality evidence reconciliation — historical only

[quality-remediation-2026-09-13.json](quality-remediation-2026-09-13.json) records
39 completed responses, 33 automatic passes, six failures, no provider errors and
39 available judgments. Its source hash is
`36a1516b3762eba3e83e386069c961f7a5da953ab3c3f113d3d1241eb32b5a53`, covering
backend sources/prompts/fixtures, runner and lock, not frontend or provider internals.
The existing remediation source is the reviewed working tree; no new application
edits were made in this pass.

That run used Groq, default `openai/gpt-oss-120b`, Writing override/judge
`qwen/qwen3.8-27b`, reasoning `low`, configured per-agent caps/temperatures and
35-second provider timeout. Effective settings are recorded on each row. Its
[quality ledger](quality-evidence-2026-09-13.md) records additional judge blind spots.
This review did not regenerate, rejudge or relabel those outputs. Older 36/39 and
6/39 partials remain historical and must not be counted as current complete runs.
Writing's same-model judge and synthetic/no-history fixtures limit independence
and generalization. Fixing application mechanisms does not close model-quality acceptance.

## Remaining gates and minimum next work

**Local use:** proceed with synthetic/noncritical data while knowing that an older
list response can hide a saved fact until reload and failed new-chat creation can
be silent. Fix R14-01–03, add regression checks, correct R14-04, and rerun affected
tests. No visual redesign is required for the functional corrections.

**Invite-only beta:** conditional hold until those fixes pass, PostgreSQL credential
races/migrations are verified, and the actual HTTPS domain is exercised for secure
cookies, account isolation, streaming, disconnect/retry and memory-failure handling.
Run the production image/rehearsal checks under its pinned runtime. Verify encrypted
schema-0004 restoration from genuinely remote storage, scheduler/retention behavior,
and delivery to an actual authorized operator. Audit any pre-hardening stored
memory using the documented process. Preserve one backend worker. Make an explicit
quality/support decision based on the existing failures before inviting users.

**Public production:** hold. All beta gates apply; additionally validate open-signup
abuse/capacity against shared provider quota, settle recovery-only support and
unverified-email policy, privacy/retention/support ownership, and complete physical
iOS/Android and screen-reader journeys. Stored backup deletion/restore responsibilities,
asset provenance, domain ownership and operator credentials require owner handover,
not an assumption that code transfers those rights or responsibilities.

Docker Desktop's Linux engine was unavailable throughout this review. Consequently
no fresh PostgreSQL, container/TLS or Linux backup/restore rehearsal is claimed.
No real notifications were deliberately sent. Temporary localhost test services
were stopped after review. No deployment, mobile implementation, application fix,
frontend design change or commit was performed.

## Authorized remediation — 2026-09-14

This appendix describes the subsequent implementation pass, not the read-only
review above. Existing working-tree changes and historical evidence were retained.

- **R14-01 fixed:** `useApi` applies only the newest request's result, error and
  loading completion. Lifecycle cleanup invalidates pending requests, and a null
  path clears stale state. The new data-hook check covers stale successes,
  failures, finalizers and navigation/unmount. The browser reproduction now keeps
  the second saved fact visible after releasing the older response.
- **R14-02 fixed:** shared explicit-null validation rejects required stored fields
  in profile, goal, shared-memory and agent-memory updates before services run.
  All 19 null-field cases return 422 and preserve stored state. Four omitted-field
  checks pass; clearing a nullable target date and a key account's nullable email
  still works. Existing genuine collision tests continue to pass.
- **R14-03 fixed:** new-conversation creation catches failures, shows the existing
  error notice (including in the history drawer), announces it, preserves the
  existing conversation/draft, and releases its in-flight guard for a retry.
  Browser fault injection now produces a useful notice with no uncaught page
  error; retry succeeds. Duplicate calls while creation is pending are ignored.
- **R14-04 fixed:** Memory now says filtering can miss sensitive details and points
  to the Account automatic-learning control. Layout, styling and artwork remain
  unchanged; the updated copy fits the checked 390px layout.

**Verification:** 351 backend tests passed; Ruff, frontend typecheck and production
build passed; frontend lint had **0 errors / 12 existing warnings** (one obsolete
suppression removed). Data-hook, stream-hook and Markdown-link checks passed. The new
Chrome regression script passed all three checks against a disposable authenticated
API with mock responses: reordered memory fetches, privacy wording/phone layout,
and failed new-conversation creation followed by successful retry. No live AI
response evaluation, dependency update or deployment was performed. PostgreSQL,
real-domain transport and operational launch gates above remain open. The prior
quality artifact is historical: backend source changed in this pass, even though
agent prompts and model configuration did not.

New reproducible checks:

```text
backend:  .venv/Scripts/python.exe -m pytest -q tests/test_september14_fixes.py
frontend: node tools/api-check.cjs
frontend: node tools/application-check.cjs
```

The browser script requires an isolated `tools.qa_server` API at port 8102,
`--frontend http://localhost:3300`, and a production frontend at port 3300.
Set `PLAYWRIGHT_MODULE` to an installed Playwright module if needed. Use a temporary
working directory/database and the helper's public synthetic QA key, never real
accounts or data. Its API bridge buffers responses; it does not measure SSE latency.

Sources: [null validator](../backend/app/core/validation.py),
[API regressions](../backend/tests/test_september14_fixes.py),
[data-hook check](../frontend/tools/api-check.cjs),
[browser regression check](../frontend/tools/application-check.cjs).
