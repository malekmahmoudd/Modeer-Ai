# Independent production-readiness review — 2026-09-13

## Baseline and scope

Reviewed HEAD `1ed17eb`, including the existing working-tree changes to `accessibility-results.json` and `launch-fixes.md`, and the untracked `quality-release-2026-09-13b.json.partial`. Those files were preserved. Read the [previous independent review and its remediation appendices](production-readiness-review-2026-09-11.md) before assessing the current implementation. This review changes documentation only.

The pass covered authentication and recovery, account ownership, memory extraction and prompt construction, conversation persistence, streaming/retry behavior, provider controls, frontend state handling, design/accessibility artifacts, dependency/build configuration, migrations, operations scripts, and quality-result provenance. It is a source and targeted-test review, not an exhaustive penetration test or a production certification.

## Fresh verification

- Backend: `cd backend; .venv/Scripts/python.exe -m pytest -q` — **319 passed**, one Starlette TestClient deprecation warning, 14.66 seconds.
- Backend: `.venv/Scripts/python.exe -m ruff check .` — passed.
- Frontend: `npm run build` — successful Next 16.3.5 production build, including TypeScript checks.
- Frontend: `npm run lint` — **0 errors, 13 warnings**. Warnings include effect/state patterns, reading refs during render, internal navigation via `location.assign`, and an unused suppression.
- Frontend: `npm audit --omit=dev --json` — **0 reported production dependency vulnerabilities**. This is an advisory lookup, not proof of exploit resistance.
- Two isolated handler/service probes using synthetic data reproduced R13-01 and R13-03 below. No real account or provider was used.
- ORM metadata inspection: **10 application tables**. Alembic adds its version table separately. Current migration head is `0004` in the migration scripts.
- Reapplied the current deterministic rubric to the six saved responses in the newest quality partial: **6/6 passed**. No generation or judge calls were made; original artifacts were not rewritten.

Not rerun: Docker image tests, PostgreSQL migration/restore rehearsal, browser rehearsal, axe scan, physical-device or screen-reader checks. `docker ps` failed because the Docker Desktop Linux engine was unavailable. `pip_audit` is absent from the current venv; Python advisory cleanliness is historical evidence, not freshly verified. Live-provider quota expenditure: zero.

## Findings

### R13-01 — High: recovery-code consumption is not atomic

**New; reproduced at handler level.** [auth.py](../backend/app/api/routes/auth.py), `recover`, lines 230–258: a request reads unused codes, matches one, sets `used_at`, changes the password and increments the previously loaded session epoch. There is no conditional database claim or row lock.

Two requests that both read the unused code can both finish successfully. The isolated probe used a temporary SQLite database, two SQLAlchemy sessions and two threads. It seeded one account and one recovery code, then invoked the actual `recover` handler twice with that same code and different new passwords. A barrier around password hashing synchronized the requests after both had matched the code. Both returned `signed_in: true` and set session cookies; the final epoch was **1**, not 2. The throttle was replaced with a no-op for this probe only; two attempts are below the real ten-attempt limit. Origin validation and the real password hashing implementation were retained.

Expected: exactly one consumption succeeds; subsequent requests fail, and credential changes invalidate the appropriate sessions. Actual: both callers receive sessions for the same epoch; the last password write wins. Exploitation requires possession of a valid recovery code and overlapping requests; this is not a recovery-code guessing bypass. PostgreSQL concurrency was not executed this turn, although the same unguarded read/write sequence exists there.

**Correction:** serialize recovery/credential changes per account in the database, atomically claim an unused code, update the password and epoch within the same transaction, and issue the session from committed state. Test simultaneous use of one code, different codes, code regeneration versus recovery, and password change versus recovery on PostgreSQL as well as SQLite. Fix before enabling password-account onboarding, including a beta that permits key accounts to set passwords.

### R13-02 — Medium: memory-update errors are discarded by the frontend

**Partially fixed prior finding RR-06; confirmed by code tracing.** The backend now correctly emits a `memory` event with `error: "Your reply was saved, but memory could not be updated."` after post-reply persistence failure. However, [useChatStream.ts](../frontend/src/features/chat/useChatStream.ts), lines 111–116, forwards only candidates and onboarding status. Its callback type has no error field. [ChatWorkspace.tsx](../frontend/src/components/chat/ChatWorkspace.tsx), lines 140–144, therefore cannot show or announce the failure.

Trigger: successful saved answer followed by a failed memory update. Expected: preserve the answer and show a distinct, accessible memory failure notice. Actual: the notice disappears. This was traced through the event producer and consumer; no new browser reproduction was performed.

**Correction:** propagate the memory error through the event type and callback, render/announce it without marking the reply failed, and test the browser path with a scripted post-answer memory failure.

### R13-03 — Medium: aggregate personal-context limits can be bypassed

**New; profile bypass reproduced.** [ProfileUpdate](../backend/app/users/schemas.py) caps each patch at 20 fields, but [update_profile](../backend/app/users/service.py), lines 67–71, merges the patch into the existing dictionary without validating the result. Two valid patches with 20 distinct 300-character values produced **40 stored fields**. Repeating this grows the profile. `_about_user` in [context.py](../backend/app/agents/context.py) injects the whole profile into every prompt.

Related code-level gap: [goal schemas](../backend/app/goals/schemas.py) leave `detail` unbounded, and `_goals_block` includes the detail of up to five active goals without a character budget. Also, `_memory_block` admits the first row even if a legacy value exceeds its budget; new-write limits do not repair old data.

Impact is primarily an account making its own prompts oversized and exhausting its allowance, plus server storage/resource cost; no cross-account data leak was demonstrated.

**Correction:** validate the merged profile, bound goal input and all injected context blocks, and audit oversized legacy values without deleting user data automatically. Include repeated updates and legacy rows in tests.

### R13-04 — Low: release evidence still has provenance and documentation inconsistencies

**Partially fixed CG-4/RR-12.** [quality_check.py](../backend/quality_check.py), `settings_fingerprint`, records a short revision plus `-dirty`, reasoning effort and timeout. Distinct uncommitted code states can share the same identifier. Per-agent temperatures/caps and full fixture/prompt hashes are not recorded. Resume validation is improved, but it does not identify every material dirty-tree change.

The newest partial labels all six responses `1ed17eb-dirty`, yet its Research row retains the now-fixed currency-code false-positive grade. Current deterministic regrading passes that same response. Do not overwrite that artifact or call this a fresh full-suite success.

[launch-fixes.md](launch-fixes.md) contains `QUALITY_RESULTS_PLACEHOLDER` and still tells the operator to decide whether to tighten Fitness/Shopping grounding, although `682f6cf` already changed those instructions. The remaining work is measurement. [DEPLOYMENT.md](DEPLOYMENT.md) claims eleven application tables at `0004`; ORM metadata has ten, plus Alembic metadata. Its sensitive-storage row also overstates a guarantee that the privacy notice correctly describes as best effort.

**Correction:** record a content fingerprint of relevant code/prompts/fixtures and effective generation/judge settings; retain per-row provenance when mixing runs intentionally. Update the current-status sections after completing a clean measurement; keep historical results intact.

## Previous findings: current disposition

| Earlier item | Current disposition |
|---|---|
| Initial scope promotion / missing sensitivity flags | Invalid scope is rejected and missing/nonboolean sensitivity flags are conservative. Explicit false negatives still depend on a keyword backstop; this limitation is disclosed. |
| Initial final-chunk loss / silent truncation | Fixed in the OpenAI-compatible provider and shared runtime; completion states are persisted and surfaced. Existing regression suite passes. |
| Initial whitespace-only chat | Request validator rejects it; tests pass. |
| #1 schema readiness | Expected heads are read dynamically; schema tests pass. |
| #2 dependency reproducibility / RR-10 | Runtime lock has hashes; production Python, Node, Postgres and Caddy images are digest-pinned. Rehearsal helper image tags still float. |
| #3 unused Ask My Team | Default off. Authenticated, quota-controlled implementation retained; no frontend caller. |
| #4 readiness flapping | Sustained-failure handling implemented. Database/schema and quota failures remain separately visible. |
| #5 prompt isolation | Provider-input and owner-decision tests now exist and pass, including shared-only team consults. |
| #6 CSP | Nonce script policy implemented; style attributes still require the documented inline-style allowance. |
| #7 links | Shared URL policy rejects protocol-relative/backslash and unsafe-scheme cases; tests pass. |
| #8 API docs | Disabled inside the production app. |
| #9 stale docs | Improved, but R13-04 remains. |
| RR-01 manual edits overwritten | Content edits acquire source `user`; automatic writes preserve them. Pinning alone does not freeze the fact. |
| RR-02 announcements | Live-region implementation restored; previous browser evidence exists. Physical assistive-technology pass remains open. |
| RR-03 memory key collisions | Handled as 409 with rollback; regression tests pass. |
| RR-04 revoked sessions | Account/epoch resolved before stream starts, allowing a real 401. |
| RR-05 retry overlap | Serialized within one process. This is explicitly not a multi-worker guarantee or general request idempotency. |
| RR-06 post-answer failure | Backend distinguishes memory failure; UI still loses it, R13-02. |
| RR-07 timeout wording | Idle and total timeouts distinguished. Frontend still has its own 50-second whole-request limit. |
| RR-08 production mock | Production rejects mock/empty provider and missing provider key. |
| RR-09 unbounded context | New memory writes capped; aggregate profile/goals/legacy gaps remain, R13-03. |
| RR-11 rule extractor filler | Trailing-word clipping and tests implemented. |
| RR-12 / CG-4 documentation and provenance | Partly addressed; R13-04 remains. |
| CG-1 sensitivity | Disclosed limitation; user can switch automatic memory off. Default is on. This is not a guarantee that every sensitive fact is detected. |
| CG-2 quality | Still incomplete for the current three-sample release configuration; see below. |
| CG-3 live runtime journey | Prior remediation records 13/13 live journey checks. Not rerun on current HEAD; does not close real-domain/browser gates. |
| CG-5 audits | Fresh npm production audit clean; prior Python lock audit recorded clean, not rerun here. |
| CG-6 accessibility | Saved axe report has 0 violations across 25 scans; keyboard evidence exists. Physical phone and completed screen-reader pass remain open. |
| CG-7 regressions | Coverage substantially expanded; 319 tests pass, but new findings lack regression protection. |
| PD-1/2/3/4/5/6/8 | Nonce CSP, reduced public metadata, pre-text failure refunds, automatic-memory switch, production sync-chat disablement, shared-only consults, and header hardening implemented. |
| PD-7 Continue | Still a new user turn requesting continuation, not regeneration or resumable transport. Document this behavior. |

## Quality evidence reconciliation

- September 12 runs: 13 cases each, recorded **12/13** passes, revision `172f857-dirty`. Historical, not current-release acceptance.
- September 13 first partial: **36/39**, recorded **32 passed / 4 failed**, revision `ee5328d`. Contains the grounding examples that motivated later prompt changes; cannot prove the fixes fail today.
- September 13 newest partial: **6/39**, recorded **5 passed / 1 failed**, revision `1ed17eb-dirty`. The single stored failure is the Research currency false positive. Current deterministic regrading is **6/6**; existing judge results are positive for these six. This does not test the remaining 33 responses, including the newest Shopping/Fitness behavior.
- Intended release example: Groq `openai/gpt-oss-120b`; Writing override `qwen/qwen3.8-27b`; reasoning `low`; per-agent caps/temperatures from source. The judge in the artifacts is `qwen/qwen3.8-27b`.
- Harness context is synthetic and has no real conversation history. Judge outcomes are fallible, especially self-grading Writing and contested assumption/concision cases. Keep human adjudication with quotations and reasons.

## Release decisions and minimum next work

**Local development:** usable; automated checks pass. Treat recovery behavior as unsafe for valuable accounts until R13-01 is fixed. No application changes were made by this review.

**Invite-only beta:** conditional hold. Fix R13-01 where password accounts are available, R13-02 and R13-03; capture a complete current quality run and real-runtime journey; verify TLS, isolation, streaming/reconnection on the actual domain; restore the current `0004` schema from real off-host storage; schedule jobs and confirm operator receipt; audit any pre-hardening memory data. Keep the documented single-worker topology.

**Public production:** hold. All beta gates apply. Additionally validate open-signup abuse resistance and capacity against the shared provider budget, settle unverified-email/recovery-only support policy and automatic-memory defaults, complete physical-phone and screen-reader checks, reconcile documentation and release fingerprints, and confirm privacy/retention/support ownership. Built signup is not evidence of a production launch.

**Mobile:** planning only. A native client still needs explicit authentication/transport contracts, durable request identity, lifecycle recovery, and store-specific consent/reporting work. See [MOBILE-ROADMAP.md](MOBILE-ROADMAP.md).

## Subsequent remediation — 2026-09-13

The findings and release decisions above describe the original review of
`1ed17eb`. This section records the later authorized fixes in the working tree;
it does not erase the original reproduction evidence.

- **R13-01 implemented:** credential-changing handlers acquire an account write
  lock through SQL before reading current credentials. Recovery additionally
  consumes the code with a conditional unused-code update. Code consumption,
  password change and session-epoch increment commit together. Authenticated
  changes recheck the caller's epoch after waiting for the lock, and newly
  issued cookies retain that transaction's epoch snapshot. Two independent
  SQLite sessions synchronized before lock acquisition now yield one success
  for one shared code; two different codes yield two successes and two epoch
  increments. PostgreSQL race verification remains a staging gate.
- **R13-02 implemented:** the memory event's error reaches the real frontend
  stream hook and the workspace's visible error notice/accessibility announcement.
  The answer retains its completed state. A scripted hook test verifies event
  delivery and answer preservation; this is not a fresh browser/screen-reader test.
- **R13-03 implemented:** profile validation checks merged state, goal details
  have a 2000-character write limit, and profile/goals/memory context bodies
  each have a 6000-character cap, including legacy records. Rejected writes
  and prompt clipping do not delete stored data. The cap is per block, not a
  global token budget; legacy privacy remediation is still an operator action.
- **R13-04 evidence handling repaired:** new quality artifacts record a SHA-256
  of backend source, prompts, fixtures and dependency lock, effective per-agent
  model settings, and per-row provenance. Resume rejects a changed or absent
  fingerprint unless explicitly overridden; overridden historical rows keep
  their old provenance. The schema count, stale quality placeholder and current
  reports are reconciled. See [quality evidence](quality-evidence-2026-09-13.md)
  for the separate live run's results and unresolved model-quality issues.

**Verification:** 326 backend tests passed, Ruff passed; frontend typecheck and
production build passed, lint had 0 errors and 13 existing warnings; stream-hook
and Markdown-link checks passed. One Starlette test-client deprecation warning
remains. No production rollout, schema migration, artwork/layout change or
mobile implementation was performed. Docker/PostgreSQL, real-domain browser,
off-host backup and operator/device gates remain unverified in this pass.

Sources: [credential handlers](../backend/app/api/routes/auth.py),
[context builder](../backend/app/agents/context.py),
[profile service](../backend/app/users/service.py),
[goal schemas](../backend/app/goals/schemas.py),
[workspace](../frontend/src/components/chat/ChatWorkspace.tsx),
[regressions](../backend/tests/test_september13_fixes.py),
[stream check](../frontend/tools/stream-check.cjs),
[evaluation runner](../backend/quality_check.py).
