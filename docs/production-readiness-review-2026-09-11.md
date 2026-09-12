# Production-readiness review — 2026-09-11

An independent, read-only review of the repository after the implementation
pass recorded in `launch-fixes.md` → "Production-readiness pass". Earlier
reports and passing tests were treated as claims to check, not as proof.

## Scope, method and what was reviewed

| | |
|---|---|
| Revision | `172f857` on `fixes/launch-readiness-20260911` (same as `origin`) |
| Working tree | 53 uncommitted paths — 34 modified, 19 untracked. Content fingerprint: `git diff HEAD --binary` SHA-256 `EC4E9AA2931E5580…`; untracked-file manifest SHA-256 `6BF4FEE715EBF1F4…` |
| Review window | 2026-09-11, 23:22–23:40 +03:00 |
| Changes made by this review | This document only. No application code, test, configuration or deployment change. Reproduction scripts ran from a scratch directory outside the repository against throwaway databases. |
| Live provider calls | **None.** No provider quota was spent. Everything needing the real model is listed as such. |

Method: read the implementation for each area; ran the automated suites;
wrote targeted reproductions with synthetic accounts, recording and scripted
providers (so the exact provider input could be inspected), and a
production-image browser session (`deploy/tests/production-rehearsal`,
built from this same working tree, then removed). Each finding below says
whether it was **reproduced** or found by **code reading**.

Categories used: **Defect** (confirmed wrong behaviour), **Coverage gap**
(unverified or unprotected behaviour), **Operational gate** (can only be
verified on the real deployment), **Product decision** (behaviour that is as
designed but needs an explicit owner call).

---

## 1. Prioritized findings

| ID | Severity | Category | Status | Title |
|---|---|---|---|---|
| RR-01 | Medium | Defect | Partially fixed | Memory-page corrections can be silently overwritten by automatic extraction |
| RR-02 | Medium | Defect | **Regression** | Failed and cut-off replies are no longer announced to assistive technology |
| RR-03 | Medium | Defect | New | Renaming a memory label onto an existing one crashes the request and pages the operator |
| RR-04 | Low–Medium | Defect | New (older code) | Revoked or deleted sessions get "The reply was interrupted" on the chat stream instead of a sign-in |
| RR-05 | Low | Defect | New | Overlapping retries answer the same message twice |
| RR-06 | Low | Defect | New (older code) | A failure after a completed reply is reported as an interrupted reply |
| RR-07 | Low | Defect | New | A slow but live stream is cut at the total timeout and labelled "stopped responding" |
| RR-08 | Low | Defect | New | Production settings accept the mock model |
| RR-09 | Low | Defect | New | Hand-saved memory values are unbounded and go into every prompt |
| RR-10 | Low | Defect | Partially fixed | Frontend, database and proxy images still float |
| RR-11 | Low | Defect | New | The rules extractor keeps trailing words ("Alexandria now") |
| RR-12 | Low | Defect (docs) | New | Documentation claims that the code or evidence do not support |
| CG-1 | Medium | Coverage gap | Known, undisclosed | Automatic sensitive-fact detection is best-effort; a health fact was stored |
| CG-2 | Medium | Coverage gap | Open | Agent-quality evidence is incomplete, mixed-provenance, and its two failures are contestable |
| CG-3 | Medium | Coverage gap | Open | The real model has not run through the final chat runtime and browser path |
| CG-4 | Low | Coverage gap | Open | Evaluation resume does not pin code revision or settings |
| CG-5 | Low | Coverage gap | Open | Dependency vulnerability scanning incomplete; a Next.js advisory is open |
| CG-6 | Low | Coverage gap | Open | No accessibility audit or physical-device test |
| CG-7 | Low | Coverage gap | Open | No regression tests for RR-01 to RR-06 or for announcements |
| OG-1…6 | — | Operational gates | Open | Real domain/TLS, off-host restore and scheduler, alert delivery, phone, memory audit on real data, finishing the quality run |
| PD-1…8 | — | Product decisions | For the owner | CSP inline allowances, public endpoints, charging failed calls, memory consent, unused routes, Ask My Team when enabled, "Continue", header hardening |

### RR-01 — Memory-page corrections can be silently overwritten by automatic extraction

- **Severity / impact:** Medium. Fix before an invite-only beta: the privacy
  notice promises people can correct what is remembered, and the implementation
  pass claimed automatic extraction never overrides a person.
- **Status:** Partially fixed. The protection added in this pass covers facts
  created with `POST` (source `user`); it does not cover facts corrected with
  `PATCH`, which is how the Memory page edits.
- **Where:** `backend/app/memory/service.py:86-97` and `:155-166` — updates
  copy fields but leave `source` as the extracting agent;
  `service.py:205` — protection checks `source == "user"` only. Routes
  `backend/app/api/routes/memory.py:36`, `:69`. UI edit form
  `frontend/src/components/memory/MemoryRow.tsx`.
- **Trigger / reproduction (reproduced, R1):** an automatic fact
  `location = Cairo` (source `modeer`) is corrected with
  `PATCH /api/memory/shared/{id} {"value": "Giza"}` → 200, source still
  `modeer`. The next chat turn "By the way I live in Alexandria now." through
  the real chat route replaced it: value `Alexandria now`. Control: the same
  sequence for a fact saved with `POST` kept `Giza`.
- **Expected vs actual:** a person's edit should outrank a later inference the
  way a hand-saved fact does; it is overwritten, and the reply's memory event
  reports it as stored.
- **Scope:** shared and private memories edited on the Memory page; both
  extractors.
- **Correction:** treat any user `PATCH` as an explicit save (set
  `source = "user"` in the update routes); add a regression test.

### RR-02 — Failed and cut-off replies are no longer announced (regression)

- **Severity / impact:** Medium (WCAG 2.1 SC 4.1.3, status messages). Fix
  before a beta that may include assistive-technology users; mandatory before
  public production.
- **Status:** Regression introduced by this pass's frontend change. At
  `172f857` every failure called `setErr(m)`, rendering `ErrorNote` with
  `role="alert"`.
- **Where:** `frontend/src/components/chat/ChatWorkspace.tsx:139-150` — when
  the server had started the turn, the handler reloads the conversation and
  sets no error, so `ErrorNote` (`:373`) never renders.
  `frontend/src/components/chat/MessageBubble.tsx:58-59` — the notice is a
  plain `<p>` with no live region.
- **Reproduction (reproduced, F1/F2, production images in Chrome):** after a
  provider failure (`qa-fail`) the failure text and *Try again* are visible,
  but no element with `role="alert"`, `role="status"` or `aria-live` contains
  any text. The same after a truncated reply (`qa-truncate`).
- **Expected vs actual:** the outcome is announced; it is silent, and focus
  stays in the composer.
- **Correction:** announce the latest unfinished reply's notice through a
  polite live region (or keep a `role="alert"` note), and make the recovery
  action discoverable. Frontend change — owner's call on presentation.

### RR-03 — Renaming a memory label onto an existing one crashes and pages the operator

- **Severity / impact:** Medium, operational. Fix before beta: an ordinary user
  action produces a false outage and a CRITICAL alert.
- **Status:** New finding; the code predates this pass.
- **Where:** `backend/app/memory/schemas.py:21-27`, `:43-48` (no validation of
  `key` on update); `service.py:94-96` (flush violates
  `uq_shared_memory_user_key` / `uq_agent_memory_user_agent_key`);
  `backend/app/core/observability.py:164-185` (each unhandled error counts and
  alerts at every multiple of `ALERT_ERROR_THRESHOLD`);
  `backend/app/api/routes/health.py:99-112` (≥ threshold, recent → degraded).
  Reachable from the Label field of the Memory page's edit form
  (`MemoryRow.tsx:66`).
- **Reproduction (reproduced, R2/O2):** two facts `a1`, `b1`; `PATCH` `a1`'s
  key to `b1` three times → three 500s (`IntegrityError`, generic "Something
  went wrong" with an incident id). `/api/health/detail` went **200 → 503
  degraded** and the operator alert **"Unhandled errors"** was sent. `PATCH`
  with `key: ""` also returns 500 (response validation); the transaction rolls
  back, so no row is damaged (verified).
- **Expected vs actual:** a 409/422 explaining the label is taken, no alert;
  actual: 500s, readiness degraded for up to 15 minutes, a page to the
  operator, and the watchdog's DEGRADED message.
- **Correction:** validate and normalise `key` on update as extraction does;
  map `IntegrityError` to 409; consider keeping client-caused errors out of the
  unhandled-error alert.

### RR-04 — Revoked or deleted sessions get a generic failure on the chat stream

- **Severity / impact:** Low–Medium. No data is exposed; the security event is
  misreported and the person is left retrying. Recommended before beta.
- **Status:** New finding; the structure predates this pass.
- **Where:** `backend/app/api/routes/chat.py:47-72` — `_resolve_user`
  (`:25-32`) runs *inside* the streaming generator, after the 200 response has
  begun, and its 401/404 `HTTPException` is caught by the broad `except`
  (`:66`) and turned into "The reply was interrupted. Please try again."
  `backend/app/api/deps.py:30` answers a deleted account's still-signed cookie
  with 404 "Unknown user" rather than 401.
- **Reproduction (reproduced):** R3 — sign in; bump the account's session
  epoch (what *Sign out every device* does); `GET /api/memory/shared` → 401
  (control); `POST /api/agents/study/chat/stream` → **HTTP 200** with one
  `error` event, the generic message. No provider call, no conversation
  created. Deleted account: `GET` → 404 "Unknown user"; stream → 200 + generic
  error. F6 — device A on the chat page, device B signs out everywhere, A sends
  a message: the generic alert appears, no redirect; navigating afterwards does
  redirect to `/login` (control).
- **Correction:** resolve the account and its epoch before returning the
  `StreamingResponse` (so a real 401 reaches the client's redirect), and answer
  unknown accounts with 401.

### RR-05 — Overlapping retries answer the same message twice

- **Severity / impact:** Low. Single-tab use is guarded (`useChatStream`'s
  in-flight check); two tabs or devices are not.
- **Status:** New; retry was introduced in this pass.
- **Where:** `backend/app/conversations/service.py:119-137` —
  `prepare_retry` checks for a completed reply but claims nothing;
  `backend/app/agents/runtime.py:78-88`.
- **Reproduction (reproduced, R4):** conversation `[user, failed]`; retry 1
  starts (placeholder removed and committed); retry 2 starts while retry 1 is
  streaming — not refused; both finish → `[user, reply, reply]`, both charged.
- **Correction:** record an in-progress turn (or claim it with a conditional
  update) and refuse a concurrent retry with 409; add a concurrency test.

### RR-06 — A failure after a completed reply is reported as an interrupted reply

- **Severity / impact:** Low.
- **Status:** New finding; code predates this pass.
- **Where:** `chat.py:66-72` (broad `except` after the runtime's `end` event);
  the runtime's post-`end` memory work.
- **Reproduction (reproduced, R7):** make memory writes fail → events
  `start, delta, end, error("The reply was interrupted. Please try again.")`;
  the reply is saved `completed`. The UI shows a whole reply under an error
  saying it was interrupted.
- **Correction:** report post-reply failures as a memory problem, not a reply
  failure.

### RR-07 — A slow but live stream is cut at the total timeout and mislabelled

- **Severity / impact:** Low. Harness latencies on the release model this
  evening were 0.5–3.1 s, far below the 35 s cap.
- **Status:** New. The whole-stream timeout predates this pass; the label is
  from it.
- **Where:** `backend/app/llm/openai_compat_provider.py:83` (`asyncio.timeout`
  around the entire stream), `:26`, `:186`.
- **Reproduction (reproduced, R12):** chunks every 0.4 s with a 1 s cap → the
  text so far is kept and labelled interrupted, "The AI provider stopped
  responding before this reply finished." — while it was still sending.
- **Correction:** separate an idle-between-chunks timeout from a total cap and
  word the notice by cause.

### RR-08 — Production settings accept the mock model

- **Severity / impact:** Low; requires a misconfiguration, but its failure mode
  is silent (canned replies, readiness ok).
- **Where:** `backend/app/core/config.py:52-68` has no provider check; the
  default is `mock` (`:81`).
- **Reproduction (reproduced, R8):** `Settings(environment="production", …,
  llm_provider="mock")` constructs without error.
- **Correction:** refuse `mock`, and a missing API key, in production.

### RR-09 — Hand-saved memory values are unbounded and go into every prompt

- **Severity / impact:** Low; self-inflicted, no cross-account effect.
- **Where:** `backend/app/memory/schemas.py:11` (`min_length` only);
  `backend/app/agents/context.py:81-90` (no size budget for memory blocks).
- **Reproduction (reproduced, R13):** a 200,000-character shared value is
  accepted (201); the next Study system prompt is 208,829 characters. Every
  turn is then charged at that size against the person's daily allowance and
  may fail at the provider.
- **Correction:** cap value length and the total memory block.

### RR-10 — Frontend, database and proxy images still float

- **Severity / impact:** Low (reproducibility). **Partially fixed:** the
  previous finding #2 is closed for the backend only.
- **Where:** `frontend/Dockerfile:1`, `:8` (`node:22-alpine`);
  `deploy/compose.yml:4` (`postgres:16-alpine`), `:33` (`caddy:2-alpine`).
- **Correction:** pin by digest with the same refresh procedure the backend
  now documents.

### RR-11 — The rules extractor keeps trailing words

- **Severity / impact:** Low. The rules path runs when LLM extraction times out
  and whenever the provider is `mock`.
- **Where:** `backend/app/memory/extraction.py:117-128`.
- **Reproduction (observed in R1):** "I live in Alexandria now." → location
  `Alexandria now`.
- **Correction:** extend clipping (now, currently, these days …) with tests.

### RR-12 — Documentation claims the code or evidence do not support

- **Severity / impact:** Low, but these are documents people act on.
- a) `docs/launch-fixes.md:453` calls Writing's `[placeholder …]` output "A real
  defect". The agent prompt *requires* it — `context.py`, final-answer rule 3:
  "In a bio or email, mark a gap with an explicit [placeholder]" — and the
  judge's `delivers` dimension (`backend/app/agents/rubric.py`) fails only an
  absent deliverable. The verdict is contested, not established (see CG-2).
- b) `backend/app/legal/privacy.md:43-47` says the provider receives the
  instructions, relevant facts and "your message". It also receives up to 40
  earlier messages of the conversation (`context.py:22`, `:205`) and, per turn,
  a second call carrying the message for memory extraction (verified in R10).
- c) `privacy.md:23-25` reads as if sensitive facts are never stored
  automatically; detection is best-effort (CG-1). `privacy.md:64` promises
  corrections that RR-01 can undo.
- d) `docs/product.md:60-64` describes Ask My Team without saying it is off by
  default.
- **Correction:** amend the text.

### CG-1 — Sensitive-fact detection is best-effort; a health fact was stored

- **Reproduced (R11):** with the model's flag `false` and no backstop keyword,
  "takes insulin before breakfast" was stored automatically as a shared
  `routine` fact. The keyword backstop is documented in `launch-fixes.md` as a
  floor, not a classifier; that limitation is not disclosed to users (RR-12c).
- **Correction:** disclose it; consider asking the person before storing
  health-adjacent candidates; widen the backstop with tests, knowing it will
  never be complete.

### CG-2 — Agent-quality evidence is incomplete, mixed-provenance, and contestable

Reconciled against the exact code and settings (`openai/gpt-oss-120b` for all
agents except Writing's `qwen/qwen3.8-27b`; reasoning `low`; per-agent
`max_tokens` 650–1600; judge `qwen/qwen3.8-27b`;
`docs/quality-launch-verified.json.partial`):

- **Incomplete:** 27 of 39 cases; sample 3 has one case. It stopped on the
  provider's daily quota (a 479 s retry-after). No complete
  `quality-launch-verified.json` exists.
- **Mixed provenance:** rows 1–4 came from the run stopped at 17:19, committed
  in `d3e2494` — code older than this pass's provider fix — and have no
  `finish` field. Their grading hit that day's quota: **ungraded**, never a
  pass. Their text ends on complete sentences, so no truncation is visible.
  Rows 5–27 are the current code.
- **Results on the current code (rows 5–27):** 21 passed, 2 failed by the
  judge; deterministic rubric 27/27 across all rows; 0 provider errors; 0
  truncated; 0.53–3.14 s harness completion time; 5–437 words.
- **Both failures are contestable:** Writing's bio followed the prompt's
  `[placeholder]` rule (RR-12a) and was graded by its own model; Career's
  `concision` evidence quotes the one-sentence trade-off the prompt requires.
  Human adjudication is needed before either counts as a defect.
- **Stale baselines:** 25/39 (regraded), 12/13 and the qwen-default runs used
  older prompts or code; none is comparable.
- **What the harness does not test:** it calls `provider.complete()` with
  synthetic context. It exercises prompts, the model and stream parsing — not
  the chat runtime, history, memory extraction, retries or persistence.

### CG-3 — The real model has not run through the final chat path

The production rehearsal used a scripted upstream; the only live browser
journey on record is from 2026-09-10, older code. The new stream handling was
exercised against real Groq streams only via the harness's `complete()` calls.
One live journey through the final runtime (chat, memory, a follow-up) is
needed; it requires live quota.

### CG-4 — Evaluation resume does not pin code revision or settings

`backend/quality_check.py:235-256` checks prompt version and model per row, not
code revision, reasoning effort or token caps, so rows from different code
states merge silently — exactly what happened in CG-2. Record the revision and
settings in the results file and refuse to resume across them.

### CG-5 — Dependency vulnerability scanning incomplete

- Python: no auditor is installed in the dev venv; **not performed** (not
  installed for this review, to avoid changing the environment).
- Frontend (`npm audit --omit=dev`): `next@15.5.25` bundles `postcss@8.4.31`
  with open advisories (1 high, 1 moderate). The fix requires `next@16.3.5`, a
  major upgrade. The advisories concern processing attacker-controlled CSS and
  source maps, which happens at build time on first-party files only here, so
  practical exposure is low; the advisory remains open.

### CG-6 / CG-7 — Accessibility, devices, and missing regression tests

No automated accessibility audit or screen-reader pass was run; 390 px checks
used desktop Chrome, not a phone. There are no tests for RR-01 through RR-06,
nor for status announcements.

### Operational gates (cannot be verified here)

| ID | Gate | Needs |
|---|---|---|
| OG-1 | Real host, domain and public TLS; cookies, streaming, reconnects and account isolation there | Owner's host |
| OG-2 | Scheduled encrypted backups to genuinely remote storage, and a restore from it | Owner's storage. Scripts reviewed and sound: mandatory encryption, byte-compared copy, locking, nightly restore from the *copied* archive. |
| OG-3 | An alert (outage, recovery, backup failure, test) reaching a person | A configured channel |
| OG-4 | A journey on a physical phone | A device |
| OG-5 | `tools.memory_audit` and the consent-based review on any database holding pre-fix data | That database |
| OG-6 | Finish the quality run and adjudicate its failures | Fresh daily quota on `gpt-oss-120b` and `qwen/qwen3.8-27b` |

### Product decisions (as designed; need an explicit owner call)

- **PD-1 CSP inline allowances.** `deploy/Caddyfile:13` keeps `'unsafe-inline'`
  for scripts and styles (Next.js inline page data, server-rendered `style`
  attributes). Nonces would need frontend middleware and per-request rendering.
  Verified otherwise effective: the exact header on documents and API
  responses, zero violations.
- **PD-2 Public endpoints.** `/api/health/detail` exposes counts, incident ids,
  error types, model names, failure streaks and auth mode (documented intent);
  `/api/agents` and `/api/agents/{id}` expose model settings and prompt
  framework bullets (`backend/app/api/routes/agents.py:37`, `:47`). Acceptable
  for invite-only; reconsider for public.
- **PD-3 Failed calls stay charged.** Documented in `backend/app/core/usage.py:5`.
  R5: one failed attempt was charged 9,972 of the default 60,000 daily units.
  With *Try again*, a few provider failures can use up a person's day.
- **PD-4 Memory consent.** There is no per-person switch for automatic memory;
  `MEMORY_STORE_SENSITIVE` is deployment-wide. The `sensitive` flag does not
  affect prompt inclusion: hand-saved sensitive facts reach any agent whose
  context filter includes their category, and always Modeer, which receives all
  shared facts (R10: excluded from Study only because Study's filter omits
  `health`).
- **PD-5 Unused but exposed route.** `POST /api/agents/{id}/chat` (synchronous)
  answers 200 in production (F7); no screen uses it. Authenticated and
  rate-limited.
- **PD-6 Ask My Team, if enabled.** Off and answering 404 (F8, R6). Before
  enabling: each specialist's answer, which can draw on its private notes, is
  passed into Modeer's synthesis (`backend/app/api/routes/team.py:111-114`),
  contrary to the Memory page's "only that agent sees them"; each consult adds an
  "Ask My Team" conversation to every chosen specialist's history and runs
  memory extraction once per specialist. While off, a signed-in caller with a
  malformed body gets 422 before the 404 (R6).
- **PD-7 "Continue".** Sends a canned English message; it is visible and
  charged.
- **PD-8 Header hardening.** `X-Powered-By: Next.js` is sent; no
  `Permissions-Policy` or `Cross-Origin-Opener-Policy` (F4).

### Checked and held

Auth: cookies are signed over the account's access-key digest and session
epoch; epoch revocation works on every `CurrentUser` route; every non-GET
cookie request needs the exact frontend origin; HttpOnly, Secure (production)
and SameSite=Strict were observed in the browser. Account isolation (R9): every
cross-account read, delete, edit, chat and retry was refused (404 /
"conversation not found"), and the other account's export held none of the
data. Prompt construction (R10): another specialist's private notes, Modeer's
private notes and another account's facts were absent from the Study prompt,
and the extraction call carried only the message. Extraction validation fails
closed on malformed candidates (code and tests). Schema readiness on PostgreSQL
in production mode (reproduced): behind head → 503; extra revision → 503;
restored → 200. Migrations match the models (`alembic check` clean; single head
`0003`). API docs are off in the production image. The image holds exactly the
lock. No message content appears in log calls (code scan). The admin dashboard
escapes interpolated strings.

---

## 2. Disposition of previous findings and claimed remediations

**Pre-production review (launch-fixes.md, 2026-09-11):**

| # | Finding | Disposition | Evidence |
|---|---|---|---|
| 1 | Readiness hard-coded the schema revision | **Resolved** | Reproduced on PostgreSQL in production mode (503 behind head, 503 extra row, 200 restored); tests |
| 2 | Backend builds not reproducible | **Resolved for the backend; partially fixed overall** | Image = lock, `pip check`, suite in image; other images float (RR-10) |
| 3 | Ask My Team live but unreachable | **Resolved (off by default)** | 404 signed in, 401 anonymous in the production image; enabling implications in PD-6 |
| 4 | Readiness flaps on one provider failure | **Resolved; new related issue** | One failure no longer degrades (tests, code); client-caused 500s can now trip readiness and alerts (RR-03) |
| 5 | Isolation tested at the query, not the prompt | **Resolved** | Independent provider-input capture (R10) and cross-account sweep (R9) |
| 6 | No CSP | **Resolved, with a decision** | Exact header on documents and API responses, zero violations; inline allowances (PD-1) |
| 7 | Markdown allowed protocol-relative URLs | **Resolved** | `links-check.cjs` (8 allowed, 21 refused); only safe links rendered in the browser |
| 8 | API docs hidden by routing only | **Resolved** | `/docs`, `/redoc`, `/openapi.json` → 404 inside the production image |
| 9 | Stale numbers in docs | **Mostly resolved** | Counts current and historical ones labelled; new inaccuracies in RR-12 |

**Earlier "remaining launch gates":**

| Gate | Disposition |
|---|---|
| 1. Answer quality on the release configuration | **Open** — CG-2, OG-6 |
| 2. Real host, domain, TLS | **Open** — OG-1 |
| 3. Scheduler, remote destination, restore from it | **Open** — OG-2 (scripts sound) |
| 4. Operator notification received by a person | **Open** — OG-3 |
| 5. Final production-browser journey | **Partially met** — production images ran in a local browser rehearsal with a scripted model; real domain and real model open (OG-1, CG-3) |

**Remediations claimed in the implementation pass:**

| Claim | Disposition |
|---|---|
| Extraction fails closed (types, scope, category, key, confidence, unknown specialists never widened) | **Verified** (code, tests, provider-input capture) |
| Model's sensitivity flag not trusted alone; keyword backstop | **Verified as described; limitation reproduced** (CG-1) |
| Automatic extraction never overwrites what a person saved | **Partially fixed** — true for `POST`, not for Memory-page edits (RR-01) |
| Memory audit is read-only | **Verified earlier** (file checksum unchanged) — not re-run here |
| Four completion states persisted, streamed and reloaded | **Verified** (rehearsal); announcements regressed (RR-02); mislabel on long streams (RR-07) |
| Partial text kept when the client disconnects | **Verified** in the browser (offline mid-reply → reload shows it) |
| Retry in place, no duplicate message, no hidden provider call | **Verified for one client; fails under overlap** (RR-05) |
| Blank messages refused before any work | **Verified** (tests; 422 in the production image; send disabled in UI) |
| Hashed dependency lock, pinned base image | **Verified for the backend** (RR-10 for the rest) |
| Ask My Team off by default | **Verified** |
| Sustained-failure readiness; quota alerts kept | **Verified** (tests, code); see RR-03 |
| CSP validated in a browser | **Verified** |
| Link policy | **Verified** |
| API docs off in production | **Verified** |
| Writing's placeholder output is "a real defect" | **Not supported** (RR-12a, CG-2) |

---

## 3. Verification results and limitations

| Check | Result |
|---|---|
| Backend suite (`pytest -q`) | 263 passed |
| `ruff check .` (backend) | Clean |
| Frontend `typecheck`, `next lint` | Clean |
| `node tools/links-check.cjs` | 8 allowed, 21 refused, renderer checks passed |
| `alembic upgrade head` + `alembic check` (SQLite) | Clean; single head `0003` |
| Schema readiness on PostgreSQL (rehearsal DB) | 200 → 503 → 503 → 200 as expected |
| Backend reproductions R1–R13, R2b, O1–O2 (throwaway SQLite, recording/scripted providers) | See findings; R9 isolation held; R10 input as designed |
| Browser F1–F9 on production images (Chrome, HTTPS on 127.0.0.1) | F1/F2 no announcement; F4 headers; F6 revocation; F7 sync route 200; F8 team 404; F9 CSP on API |
| `npm audit --omit=dev` | 1 high, 1 moderate (next → postcss) |
| Python dependency audit | Not performed — no auditor available |
| Live provider | Not used; 0 tokens |

Limitations: reproductions mostly ran on SQLite (PostgreSQL only for
readiness and in the rehearsal); the rehearsal images were built earlier this
evening from this same working tree (no code has changed since — see the
fingerprint); TLS came from Caddy's local CA; the phone-width checks used
desktop Chrome; no screen reader or accessibility scanner was used; no
real-model journey was run; concurrency was reproduced in-process with two
database sessions, not with two browsers. The in-process
`TestClient` streaming path was used for R3/R7; F6 confirmed R3 end to end in
the browser.

---

## 4. Readiness decisions

| Level | Decision |
|---|---|
| **Local use** (the owner, own machine) | **Ready.** The defects found affect edge cases, operators or other users; none blocks personal use. |
| **Invite-only beta** | **Not ready.** Achievable with a short list of fixes and the owner's deployment steps (below). |
| **Public production** | **Not ready.** Everything required for the beta, plus the items below, plus an account model for the public: today's access is operator-issued invitation keys; public signup and recovery are not built. |

## 5. Minimum remaining work

**Local use:** none required. Optional: RR-01 and RR-03 to avoid surprises on
the Memory page.

**Invite-only beta (minimum):**

1. Fix RR-01 (protect Memory-page edits), RR-02 (announce unfinished replies),
   RR-03 (label collisions: 409, no alert). Add regression tests for each.
2. Fix RR-04 (real 401 on the stream) — strongly recommended.
3. Correct the privacy notice and docs (RR-12b–d; CG-1 disclosure) and the
   unsupported "real defect" claim (RR-12a).
4. Finish the quality run on fresh quota and have a person adjudicate the
   failures (OG-6, CG-2); run one real-model journey through the final runtime
   (CG-3). Both need live quota.
5. Owner's deployment gates: OG-1 (host, domain, TLS), OG-2 (scheduled
   off-host backups and a restore from them), OG-3 (an alert reaching you);
   OG-5 if any pre-fix data is carried over.
6. Decide PD-3 (charging failed calls) and PD-4 (memory consent) — or accept
   them explicitly for the beta.

**Public production (in addition):**

1. Fix RR-05 through RR-11, with tests.
2. Accessibility audit and screen-reader pass; physical-device testing (CG-6,
   OG-4).
3. Resolve the Next.js advisory (major upgrade; frontend owner's call) and run a
   Python dependency audit (CG-5); pin the remaining images (RR-10).
4. Record code revision and settings in evaluation results (CG-4) and repeat
   the quality evaluation on the final configuration.
5. Decide PD-1 (nonce CSP), PD-2 (public endpoints), PD-5 (unused route), PD-6
   (before enabling Ask My Team), PD-8 (headers).
6. Build or choose the public account model (signup, recovery).

No production readiness is claimed at any level beyond local use.

---

## Appendix — remediation status (added 2026-09-12)

The findings above are the review as it stood on 2026-09-11; nothing in them has
been edited. This appendix records what happened next. Details and evidence:
`launch-fixes.md` → "Review remediation — 2026-09-12".

| ID | Disposition |
|---|---|
| RR-01 | **Fixed** — a `PATCH` records the fact as the person's; extraction leaves it alone. Test: `test_a_corrected_memory_is_not_overwritten_by_later_extraction` |
| RR-02 | **Fixed** — polite live region on the chat page; verified in the production images |
| RR-03 | **Fixed** — 409 with a readable message; readiness and alerts untouched; keys and values validated and bounded |
| RR-04 | **Fixed** — the account resolves before the stream starts, so a revoked session gets 401 and the client redirects to sign-in |
| RR-05 | **Fixed** — turns in a conversation are serialised per process; a second retry is refused with 409 |
| RR-06 | **Fixed** — a memory failure after a finished reply is reported as a memory failure |
| RR-07 | **Fixed** — idle and total timeouts are separate and worded by cause |
| RR-08 | **Fixed** — production refuses the mock model and an empty API key |
| RR-09 | **Fixed** — 2000-character values, 6000-character memory block |
| RR-10 | **Fixed** — frontend, database and proxy images pinned by digest |
| RR-11 | **Fixed** — trailing filler dropped, with tests |
| RR-12 | **Fixed** — privacy notice, `product.md` and the unsupported "real defect" claim corrected |
| CG-1 | **Disclosed** — the privacy notice now says detection is best effort; the behaviour is unchanged and remains a product decision (PD-4) |
| CG-2 | **Closed for a single sample** — a complete 13-case run on the final code: 12/13, provenance recorded in the results file. The 2026-09-11 partial stays as the record of the earlier attempt. Multi-sample variance remains unmeasured |
| CG-3 | **Closed** — `journey_check.py` passed 13/13 against the real model on the final code |
| CG-4 | **Fixed** — results record code revision and settings; a resume across a different revision is refused unless `--allow-code-change` |
| CG-5 | **Python: fixed** — audit run; Starlette advisories cleared by the FastAPI 0.141.1 / Starlette 1.6.0 upgrade; audit now clean. **Frontend: open** — `next` → `postcss` needs a major Next upgrade (owner's call) |
| CG-6 | **Open** — still no accessibility scanner run and no physical device; the announcement gap it was measuring (RR-02) is fixed |
| CG-7 | **Fixed** — `tests/test_review_fixes.py` plus three new rehearsal checks |
| OG-1…6 | **Open** — owner gates, except OG-6, which is now a complete single-sample run (see CG-2) |
| PD-1…8 | **Open decisions**, unchanged, except PD-6, which is now recorded in `product.md` |

One defect was found *by* the remediation work and fixed: message ordering fell
back to a random id when two messages shared a timestamp, so a reply could sort
before the question it answered. It was latent at the time of this review.

A second pass over that same day's changes, before deployment, found and fixed
three regressions it had introduced: the new idle timeout also capped the wait
for the first token (15s instead of 35s); recording a hand edit as the person's
own was applied to a pin as well, which froze the fact against later updates;
and the FastAPI upgrade dropped the `/api` prefix from logged route templates.
Each is covered by a test.

Answer quality had two measured defects — an invented month (quality suite, 1 of
13) and a question-only reply (live journey, 2 of 3 runs). Both were
instruction-following failures by the model. The two shared rules they broke
were tightened the same day and every agent's `prompt_version` bumped; measured
before and after on the live model, neither defect recurred (0 of 4 each) and
the 13-case suite held at 12/13 with total length slightly down. Four samples a
case is thin evidence: a three-sample suite run on fresh quota is the next
measurement. One journey check was found to be keyword-based and failing a good
answer; it now grades deterministically.

## Appendix — owner decisions (added 2026-09-13)

The owner decided the product questions and asked for them to be implemented, on
top of commit `ee5328d`. Evidence: `launch-fixes.md` → "Owner decisions
implemented — 2026-09-13".

| Item | Status |
|---|---|
| PD-1 | **Done** — per-request nonce with `'strict-dynamic'` for scripts (`frontend/src/proxy.ts`), no `'unsafe-inline'` for scripts; styles keep it for `style=""` attributes. Checked in the rehearsal: nonce differs per request, zero violations |
| PD-2 | **Done** — anonymous health bodies reduced to up/down fields; full readiness only for `ADMIN_ACCOUNTS`; agent detail no longer shows model settings or framework. The agent *list* already showed only public fields |
| PD-3 | **Done** — a provider failure before any text is refunded; partial replies and cancellations stay charged |
| PD-4 | **Partly done** — a per-person switch for automatic memory. Unchanged: hand-saved sensitive facts still reach agents whose context filter includes their category, and Modeer |
| PD-5 | **Done** — the synchronous chat route answers 404 in production |
| PD-6 | **Done for private notes** — a consult uses shared context only and runs no extraction. Unchanged: each consult still adds an "Ask My Team" conversation to each chosen specialist's history, and a malformed body gets 422 before the 404 while off |
| PD-7 | **Open** — not part of this request |
| PD-8 | **Done** — no `X-Powered-By`; `Permissions-Policy` and `Cross-Origin-Opener-Policy` sent |
| CG-5 (frontend) | **Fixed** — Next 16.3.5; `npm audit --omit=dev` reports 0 |
| CG-6 | **Partly done** — axe-core scan at two widths and a keyboard pass; only colour contrast fails (owner's design call). No physical device, no real screen reader |
| Public production account model | **Built** — open signup behind `SIGNUP_ENABLED`, passwords, single-use recovery codes, throttles. No email reset, by design |
