# Handoff — hardening pass (2026-09-10)

Written for an assistant picking this up with no prior conversation. Read this
top to bottom before changing anything; it records constraints and failure modes
that are not visible from the code alone.

## Current update — owner decisions implemented (2026-09-13)

On top of commit `ee5328d`, per the owner's choices (open signup, password,
recovery codes, memory on with a switch). Details and evidence:
`launch-fixes.md` → "Owner decisions implemented — 2026-09-13".

- **Accounts:** `SIGNUP_ENABLED` (default off) opens `/signup`; scrypt
  passwords; ten single-use recovery codes (hashed); `/recover`; change
  password and regenerate codes on Account; throttles; schema **0004**.
  Invitation keys still work and are no longer required to start. No email
  reset by design; `provision_user.py --rotate --clear-password` is the
  operator's last resort.
- **Consent and privacy:** per-person automatic-memory switch; Ask My Team uses
  shared context only and learns nothing; provider failures before any text are
  refunded.
- **Public surface:** minimal anonymous health bodies (full detail for
  `ADMIN_ACCOUNTS`), agent detail without model settings, sync chat 404 in
  production.
- **Frontend (owner-authorised for these items only):** Next 16.3.5, nonce CSP
  in `src/proxy.ts`, signup/recover pages, Account additions. File list in
  launch-fixes.md. The standing rule is unchanged: **do not edit the frontend
  unless asked.**
- **Accessibility:** axe-core scan and keyboard pass (`accessibility-check.cjs`)
  — only colour contrast fails (pink buttons 3.27:1), left for the owner. No
  real screen-reader pass yet.

Numbers: **314 backend tests** (also inside the image), rehearsal **23/23**,
frontend audit 0 vulnerabilities. Three-sample quality run partial at **32/36**
with two real grounding lapses (Fitness invented dumbbell weight, Shopping
unsupported price) — see launch-fixes.md.

Trap found this pass: on a client-side navigation the old page's fields are
still there for a moment. A Playwright check that filled "Email" right after
clicking a link filled the login form, not the recovery form. Wait for the new
page's heading first.

## Earlier update — review remediation (2026-09-12)

An independent read-only review (`docs/production-readiness-review-2026-09-11.md`)
found twelve defects and several gaps; all of the code findings are now fixed,
each with a regression test. Read `launch-fixes.md` → "Review remediation —
2026-09-12" for the list and the evidence. Highlights:

- A correction made on the Memory page is now the person's and is never
  overwritten by automatic extraction.
- Failed, truncated and interrupted replies are announced to assistive
  technology (a regression from the pass below).
- A duplicate memory label answers 409 instead of a 500 that degraded readiness
  and paged the operator.
- A revoked session gets 401 from the chat stream, so the client sends the
  person to sign in.
- **Latent bug found while fixing those:** messages written in the same clock
  tick ordered by a random id, so a reply could sort before its question.
  `add_message` now assigns a strictly increasing time per conversation.
- **Dependencies upgraded to FastAPI 0.141.1 / Starlette 1.6.0** after
  `pip-audit` reported 14 advisories against Starlette 0.46.2; the audit is now
  clean. Note FastAPI 0.141 keeps included routers nested, so `app.routes` no
  longer lists them — `tests/test_auth.py` reads the generated schema instead.

A second pass over that day's own changes caught three regressions it had
introduced — the idle timeout also capping the first token, pinning a fact
freezing it against updates, and logs losing the `/api` prefix — all fixed with
tests. Re-check work you have just done; the first pass missed all three.

Current numbers: **283 backend tests**, Ruff clean; the suite also passes inside
the production image; the production rehearsal passes **19/19** in Chrome; the
release-configuration quality run is complete at **12/13**
(`docs/quality-release-2026-09-12.json`); the live journey's application steps
all pass.

**Answer quality: two measured defects, both fixed in the prompt and
re-measured.** Study turned "final on the 20th" into "20 May", and answered
"What should I revise first?" with a clarifying question alone. Rules 2 and 3 in
`app/agents/context.py` were tightened and every agent's `prompt_version` bumped.
On the live model neither recurred (0 of 4 samples each, and 0 of 13 in the
suite); the suite held at 12/13. That is thin evidence — run
`quality_check.py --samples 3` on fresh quota before treating quality as closed.
While checking this, a keyword-based check in `journey_check.py` was found
failing a good answer and was made deterministic: read §7 before trusting any
keyword assertion.

Still not verified: a real domain and public TLS, a restore from off-host
storage, an alert reaching a person, a physical phone. Production readiness is
still not claimed.

## Earlier update — production-readiness pass (2026-09-11, evening)

Read `docs/launch-fixes.md` → "Production-readiness pass" first. It records what
changed, the evidence, the exact commands, the release configuration and the
remaining gates. In short:

- **Memory extraction fails closed.** Malformed candidates, unknown specialist
  ids and invalid scopes are dropped, never widened to shared memory; the
  model's sensitivity flag is not trusted alone; automatic extraction cannot
  overwrite what a person saved by hand. `tests/test_prompt_isolation.py` proves
  isolation at the provider's input through real HTTP requests.
  `tools/memory_audit.py` (read-only) plus a documented, consent-based process
  handle memories stored under the old rules.
- **Every reply records how it ended** — completed, truncated, interrupted or
  failed — from provider to database to API to screen, and survives a reload.
  `retry: true` regenerates the latest unfinished turn in place, only on a
  click. Blank messages are refused before any work.
- **Release items:** hashed `backend/requirements.lock` and a digest-pinned base
  image; Ask My Team off by default (`TEAM_ENABLED`); readiness degrades on
  sustained provider failure, not one blip; CSP in `deploy/Caddyfile`; Markdown
  link policy in `frontend/src/lib/links.ts`; API docs off in production.
- **Evidence:** 263 backend tests; the suite also passes inside the production
  image; a local production rehearsal (`deploy/tests/production-rehearsal/`)
  passed 16/16 browser checks with zero CSP violations.
- **Quality gate still open:** the release-configuration run stopped on the
  daily quota at 27/39 (21 pass, 2 fail, 4 ungraded). Resume it on a fresh
  budget with the command in launch-fixes.md; check `tools.provider_doctor`
  first. Writing left a literal placeholder in one bio.

The owner authorised scoped frontend changes for this pass only (completion,
error and recovery states; link handling). Every frontend file touched is listed
in launch-fixes.md. The standing rule is unchanged: **the owner edits the
frontend; do not change it without being asked.**

Not verified, and not to be claimed: a real domain and public TLS, a restore
from genuinely off-host storage, an installed scheduler, delivery of an alert to
a person, a physical phone. Production readiness is not claimed.

Repo state: branch `fixes/launch-readiness-20260911`, based on `172f857`. All of
this pass is **uncommitted** in the working tree (§3 below describes an older
branch). Commit, push or merge only when the user asks.

## Earlier update — 2026-09-11

Earlier completion claims below are historical.
This pass fixed export after a briefing, private exception/URL logging, provider
readiness and alert cooldown/delivery handling. It added Account, public Privacy,
and history deletion controls. Linux backup/restore and failure notifications
were rehearsed with disposable PostgreSQL 16 data at schema 0003.

A further defect was found: shared memories categorized as preferences were
filtered out of specialist requests. The live and evaluation paths now use the
same filter, including shared preferences while preserving private-note isolation.

Free providers remain mandatory. Do not promote a model solely because keyword
checks pass, do not remove failing rows, and preserve Writing's configured model.
Quality generation and judge availability are separate results. The former judge
omitted the synthetic profile/name and could accept incomplete dimensions; those
errors are fixed. Saved responses are regraded without regenerating them.

Hosting/domain, real TLS, physical off-host storage, installed schedules, real
operator delivery and final public-domain journeys remain owner/deployment checks.
Do not merge main or publish without the user. The local production frontend
startup was rejected by automatic approval review with only "blocked by policy";
do not relabel the successful development-browser checks as production checks.
(Superseded that evening: the production images, frontend included, ran locally
in the production rehearsal — see the update above.)

## Update: account limits and browser QA (2026-09-10)

Read `docs/STATUS.md`, `docs/usage-limits.md`, and `docs/browser-qa.md` first.
The historical pass below is retained as context. Task 1 is now implemented;
browser automation is available and has been exercised in the current environment.
Backend tests now total 112. Revision 0002 adds a tenth table for usage counters.
The old statements that there is no rate limiting, or that browser QA needs the
user, are superseded. Public hosting, baseline-model repeated quality evaluation,
and populated-database recovery remain open. Do not merge main without the user.

Companion docs, in the order they become useful:
`docs/STATUS.md` (current state of the project) · `docs/agent-quality.md` (how agents
are graded) · `docs/DEPLOYMENT.md` (runbook) · `README.md` (architecture).

---

## 1. Project in one paragraph

Modeer is a personal AI assistant plus nine specialist agents (Study, Travel,
Shopping, Career, Finance, Fitness, Writing, Research, Email) that share one
personal-context store. `frontend/` is Next.js App Router + React + TypeScript +
Tailwind. `backend/` is a FastAPI modular monolith — Python, Pydantic,
SQLAlchemy, Alembic, PostgreSQL — with **one shared agent runtime**; an agent is
configuration (`backend/app/agents/<slug>/config.py` + `prompt.md`), never a
separate service. `deploy/` holds the container stack.

---

## 2. Hard constraints — do not violate these

1. **Free tier only, permanently.** The user has decided Modeer stays on Groq's
   free tier and free models for the life of the project. **Never propose a paid
   plan as the answer to a rate limit.** The budget is **200,000 tokens per day
   per model**, and each model has a separate budget.
2. **The comic visual design is approved and settled.** Do not redesign the
   frontend. The name "Modeer" is fixed.
3. **Never commit** real credentials, `.env` files, user databases, backup
   archives, or `invite.json`. All are gitignored; keep it that way.
4. **Do not loosen a rubric threshold to make a case pass.** See §7 — this is the
   single most important convention in the repo right now.
5. This is **invite-only, pre-deployment**. Nothing is publicly deployed, no
   hosting account or domain exists.

---

## 3. Repo state

- Branch **`hardening/quality-auth-deploy`**, pushed to
  `origin` (github.com/malekmahmoudd/Modeer-Ai). Working tree clean.
- **`main` has NOT been merged.** The user has not decided whether to
  fast-forward or open a PR. Ask before merging.
- Seven commits, oldest first. Each passes its own tests standalone, so `git
  bisect` works — preserve that property.

| SHA | Subject | Tests at that commit |
|---|---|---|
| `dc18fc4` | Finish the Sunshine & Ink interior pass | — |
| `d6a8f05` | Bound provider requests and surface failures honestly | 61 |
| `fd88675` | Put every personal-data route behind invite-only authentication | 69 |
| `6acc749` | Grade agent replies on what they say, not which words they contain | 101 |
| `5e52e99` | Add the deployment stack, provisioning and backups | 101 |
| `a747c0e` | Fold the throwaway scripts into backend/tools and update STATUS | 101 |
| `7d6b7c0` | Run the container stack for real and fix what that found | 101 |

Commit messages in this repo explain **why**, and state plainly what was *not*
verified. Match that; do not write "fix stuff".

---

## 4. Environment and commands

Windows. Python venv at `backend/.venv`. Use `.venv/Scripts/python.exe`
explicitly — the venv is not auto-activated.

```sh
# backend: tests, lint
cd backend
.venv/Scripts/python.exe -m pytest tests/ -q          # expect 283 passed (2026-09-12)
.venv/Scripts/python.exe -m ruff check .              # expect clean

# frontend (do not modify; verify only)
cd frontend && npm run build && npm run lint && npm run typecheck
node tools/links-check.cjs                            # Markdown link policy

# backend image: installed set == requirements.lock, then the suite inside it
# (from the repository root; see docs/DEPLOYMENT.md)
docker build -t modeer-backend:check backend
docker run --rm -v "$PWD/backend/tests:/app/tests:ro" \
  -v "$PWD/deploy/tests/image-check.sh:/image-check.sh:ro" modeer-backend:check sh /image-check.sh

# read-only audit of automatic memories stored under the old extraction rules
.venv/Scripts/python.exe -m tools.memory_audit --list

# provider health + remaining token budget — RUN THIS BEFORE ANY LONG MODEL RUN
cd backend && .venv/Scripts/python.exe -m tools.provider_doctor

# live agent-quality run (paced, judged, writes full responses to docs/)
.venv/Scripts/python.exe quality_check.py

# everyday journey against a live provider, isolated DB
.venv/Scripts/python.exe journey_check.py

# throwaway backend with auth on, for manual browser QA (prints an access key)
.venv/Scripts/python.exe -m tools.qa_server
```

**`ruff format` is NOT enforced repo-wide.** 27 pre-existing files fail
`ruff format --check`. Do not reformat them — it creates a large unrelated diff.
Only keep files *you* touch format-clean.

---

## 5. What is verified vs not

"Verified" means it was executed and observed, not read.

### Verified

- **Agent quality**: 8/13 → 12/13 on the identical rubric. Replies run 27–381
  words where four used to run 540–735. Full responses stored in
  `docs/live-quality-*.json`.
- **Auth**: every personal-data route requires a session, enforced by a test that
  walks the real FastAPI route table (`tests/test_auth.py`). Session expiry, key
  revocation, foreign-secret cookies and origin checks all covered.
- **Live journey** (`journey_check.py`): 12/12 against a real provider — login,
  cookie flags, onboarding, LLM memory extraction, cross-agent recall, separate
  histories, mid-stream interruption, retry, no orphaned rows.
- **Container stack**: images build; Alembic applies the schema to PostgreSQL 16
  (nine tables at revision 0001, as it then was; ten since 0002); the documented bootstrap works; HTTPS, auth and the frontend
  serve through Caddy; data *and sessions* survive `down`/`up`.
- **Streaming through Caddy is not buffered**: 288 SSE events over 0.95s with 40
  gaps above 10ms.
- **Backup/restore**: dump → archive verification → AES-256 → off-host copy →
  decrypt → restore into a scratch DB with matching row counts. An archive also
  decrypts with stock `openssl` and lists all nine tables under `pg_restore`,
  using none of the repo's scripts.

### Not verified

- **11 of 13 quality cases on `openai/gpt-oss-120b`** (the baseline model). The
  complete after-run is on `qwen/qwen3.8-27b` because the 120b daily budget was
  spent. A later attempt got 2 of 13 through; both passed.
- **TLS for a real domain.** The local run used `DOMAIN=localhost`, so only
  Caddy's internal CA was exercised. Let's Encrypt needs a public hostname.
- **Restoring over a populated database.** Only empty-scratch restores.
- **Browser and mobile.** No browser automation exists in that environment. The
  real login page, mobile reconnects, and navigating away mid-reply are untested.
- **Per-user rate limiting does not exist at all.** See §6, task 1.

---

## 6. Remaining work

Each task lists where to work and what "done" means. Tasks 1–4 need no input
from the user; 5–8 are blocked on them.

### 1. Per-user rate limiting — highest priority

**Why:** there is none. One account can drain the shared 200k/day budget — which
happened during this pass. On a permanent free tier this is a product
constraint, not a dev annoyance, and it blocks inviting anyone.

**Where:** `backend/app/core/config.py` (settings),
`backend/app/api/deps.py` or `backend/app/core/auth.py` (enforcement point —
auth already resolves the caller id there), `backend/tests/`.

**Done when:** a per-account requests/minute limit and a daily token ceiling are
enforced on the chat and team routes; exceeding either returns a clear message
in the same voice as the existing provider errors (see `ProviderError` in
`backend/app/llm/openai_compat_provider.py` — user-facing text never leaks
upstream bodies); limits are configurable via settings; tests cover both the
allowed and exceeded paths.

**Watch for:** the limit must key off the authenticated session, not a header —
`X-User-Id` is attacker-controlled when auth is on. See `caller_id`.

### 2. Confirming quality run on the baseline model

**Done when:** `quality_check.py` completes all 13 cases on
`openai/gpt-oss-120b` and the result is recorded in
`docs/live-quality-results.json` with the comparison updated in
`docs/agent-quality.md`.

**Watch for:** needs a mostly idle day for quota. Check
`python -m tools.provider_doctor` first. The harness aborts cleanly on a daily
cap (exit code 2) and writes to `<out>.partial` so it cannot destroy the last
complete run — do not "fix" that by making it overwrite.

### 3. Multi-sample the evals

**Why:** single samples flip between runs — Career failed on length in one run
and passed the next; Research came in under the ceiling then three words over.
12/13 therefore means "no defect visible in this sample", not a guarantee.

**Done when:** `quality_check.py` can run each case N times and report per-case
pass rates rather than a single verdict.

**Watch for:** token cost. Prefer three samples on the historically worst agents
(study, career, research, finance) over all thirteen cases.

### 4. Rehearse a restore over a populated database

**Done when:** `deploy/restore-check.ps1` — or a documented procedure — has been
shown to recover a database that already has rows, not just an empty scratch one.

### 5. Pick a host and domain → real TLS *(needs the user)*

**Done when:** the stack runs on a public hostname, Caddy obtains a Let's Encrypt
certificate, and streaming still works through it.

### 6. Browser and mobile QA *(needs the user)*

`python -m tools.qa_server` prints an access key. Needs a human to drive the real
login page, a mobile reconnect, and navigating away mid-reply.

### 7. Merge to main *(needs the user's decision)*

### 8. Rotate the Groq API key *(needs the user)*

Hygiene only. **Confirmed it is not in git history** — `.env.example` has always
had `LLM_API_KEY=` empty. Do not tell the user the repo is compromised.

---

## 7. Conventions you must follow

### The rubric philosophy — read this before touching `app/agents/rubric.py`

The old scoring checked whether a reply contained the right keywords. It passed a
biography full of invented achievements, a study plan that guessed a month and
then withheld itself, and a shopping answer quoting stale prices confidently.

The replacement (`backend/app/agents/rubric.py`) has two layers:

- `review()` — deterministic, no provider, safe for CI. **High precision by
  design**: a violation must mean a real defect, because these gate the build.
- `judge()` — an LLM judge for what a regex cannot see, required to quote the
  span it objects to. A judge outage records as *unavailable*, never as a failed
  case.

**The rule: when a check fires on a good reply, make the check more precise —
never relax a threshold so a sample passes.** Six false positives were fixed this
way, each pinned by a test in both directions (`tests/test_rubric.py`). Examples:

- `must_avoid` matched substrings, so "Friday-to-Sunday **trip**" contained "day
  trip" and failed a single-city itinerary that had honoured the preference.
- "Check current prices" was read as a capability claim, when telling the user to
  check is the *wanted* behaviour. Every alternative now needs a first-person
  subject.
- Budget lines (`**Buffer:** £50`) were read as market price claims.

`docs/live-quality-*.json` stores **full responses**, precisely so the rubric can
be changed and re-applied for free. Re-grade rather than re-run the model:

```sh
cd backend && .venv/Scripts/python.exe -c "
import json; from app.agents.evals import load_cases; from app.agents.rubric import review
fx={c['id']:c for s in ['modeer','study','career','research','writing','travel',
    'shopping','finance','fitness','email'] for c in load_cases(s)}
d=json.load(open('../docs/live-quality-results.json',encoding='utf8'))
for r in d['results']:
    v=review(fx.get(r['case'],{'input':r['input'],'expect':{}}), r['output'])
    print(('PASS' if v.passed else 'FAIL'), r['case'], v.words, [x.code for x in v.violations])"
```

### The LLM judge is an aid, not an oracle

`openai/gpt-oss-20b` produces regular false positives. Read the stored responses
before acting on a verdict. Prefer a judge model that is not the model under test.

### Agent prompt changes

Agent behaviour lives in `backend/app/agents/<slug>/config.py`; shared rules live
in `_GLOBAL_GUARDRAILS` and the "Final answer requirements" block in
`backend/app/agents/context.py`. Bump `prompt_version` when you change behaviour.

Two lessons already paid for: rules written as a **paragraph were reliably
ignored** — the guardrails are now numbered imperatives. And a **structural
budget beats a word count** ("recommendation in one or two sentences, the
trade-off in two or three, then at most three next actions") — that took Career
from 452 words to 299 and improved the content.

---

## 8. Traps — each of these silently produced a wrong answer

1. **A passing test can hide a broken backup.** Piping the passphrase through
   PowerShell appended a carriage return. Archives round-tripped through the
   repo's own scripts because both ends carried the same stray byte, but would
   **not** decrypt with plain `openssl` on Linux — the one case a backup exists
   for. The passphrase file is now mounted and read by openssl directly. If you
   change how it reaches openssl, re-run the manual decrypt in
   `docs/DEPLOYMENT.md`.
2. **The mock provider cannot test SSE buffering.** It emits every event inside
   one millisecond, so events arrive together whether or not the proxy buffers.
   Only a live reply answers the question.
3. **Git Bash rewrites container paths.** `docker cp c:/tmp/x.json .` becomes a
   mangled `C:/Users/.../Temp/x.json`. Use PowerShell, or prefix
   `MSYS_NO_PATHCONV=1`.
4. **PowerShell treats a native command's stderr as fatal** under
   `$ErrorActionPreference = 'Stop'` — one psql `NOTICE` aborted the restore
   check despite exit code 0. Check `$LASTEXITCODE` instead.
5. **`postgres:16-alpine` has no openssl.** The scripts use a pinned
   `alpine/openssl:3.5.8`.
6. **Rate limits masquerade as quality failures.** Two early runs scored 429s as
   empty, bad answers. The harness now distinguishes a per-minute throttle from a
   daily quota via `ProviderError.retry_after` (a number from the header — never
   upstream body text).
7. **Auth must resolve before body validation.** `chat/stream` used to return 422
   before 401, leaking the request schema to anonymous callers. Auth is now a
   FastAPI dependency (`core.auth.caller_id`). If you add a route that touches
   personal data, the route-table sweep in `tests/test_auth.py` will fail until
   it is covered — fix the route, not the test.

---

## 9. Definition of done for this phase

Deployment-ready means, at minimum: task 1 complete; tasks 5 and 6 done with the
user; the stack running on a real domain with a real certificate; and
`docs/STATUS.md` updated to say so. Until then the project is **not** deployable,
and `docs/STATUS.md` §1 should keep saying that.
