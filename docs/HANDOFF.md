# Handoff — hardening pass (2026-09-10)

Written for an assistant picking this up with no prior conversation. Read this
top to bottom before changing anything; it records constraints and failure modes
that are not visible from the code alone.

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
.venv/Scripts/python.exe -m pytest tests/ -q          # expect 101 passed
.venv/Scripts/python.exe -m ruff check .              # expect clean

# frontend (do not modify; verify only)
cd frontend && npm run build && npm run lint && npm run typecheck

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
  (nine tables); the documented bootstrap works; HTTPS, auth and the frontend
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
