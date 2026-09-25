# Project status — Modeer Personal AI Team MVP

_Last updated: 2026-09-25 · phase: production readiness, invite-only or open signup_


## Current: verified, with screens — 2026-09-25 (end of day)

- **Image.** Built and verified for `linux/amd64` on Colima: exact lock set,
  446 tests inside the image, model and `tzdata` working, 801 MB, non-root.
  Building it caught one bug: `fetch_model.py` failed when run from `/tmp`.
- **Live evals against Groq.** The regression set scored 11/13 before fixes.
  The two failures, and later ones, were traced to the shortened rules and
  fixed. After the fixes:
  - Shopping 2/2, Travel pass, Leo 2/2, Emma 1/2 (an arithmetic slip).
  - All 10 crisis cases put safety first, including domestic abuse.
- **Dates.** Weekday arithmetic came from the model's training-year calendar
  ("Thursday 2 October"). Date words are now resolved in code
  (`clock.resolve_dates`) and given to the agent as facts.
- **Memory analysis, checked live on six messages:**
  - valid JSON with events, check-ins, handoffs, goal ops and outcomes
  - the physio appointment held back
  - Arabic handled
  - the pasted email ignored
- **Judge.** Its premise was updated: the app really does pass notes to
  teammates. The judge version is now 3.
- **Screens, built from the existing components:**
  - Plans page
  - Memory page: files section, and "why it knows" with undo
  - a sources line under replies
  - Plans in the navigation

  Checked in Chrome at 1440 px and 390 px, with no page errors.

## Earlier: documents (RAG v1) — 2026-09-25

People can give files (PDF, DOCX, TXT, MD; 10 MB; 5 per account) to an agent.
`docs/rag.md` has the details.

- **Storage.** Parsing is sandboxed, only the extracted text is kept, and the
  file is discarded.
- **Search.** A local multilingual embedding model (MIT, pinned and
  checksum-verified at build) plus keyword search, with a relevance gate.
- **Answers.** Cited passages go in the user's turn, never into history,
  summaries or memory. Documents are private to their agent unless shared.
- **Eval set.** 41 labelled questions, no LLM calls. Hybrid search gets recall
  0.87 and MRR 0.82, with no off-topic leaks.
- **Schema 0007. 444 backend tests.**
- **Image.** Verified later the same day (see above). pip-audit on the full
  lock found no known vulnerabilities.

## Earlier: council fixes — 2026-09-25

A council of 50 independent expert reviews looked at the day's work. I fixed
their top findings; **420 backend tests** pass.

- **Data fixes:**
  - An allergy can no longer be overwritten by a diet preference.
  - Plan progress no longer ticks on negations or questions.
  - Follow-ups and check-ins now fail closed on sensitive data. The keyword
    list covers medical, eating, crisis, life-event and Arabic terms.
  - Arabic and French pasted emails are ignored.
  - Stored text can no longer break out of its prompt block (`app/core/text.py`).
  - Sensitive chat titles are hidden from Leo.
- **Behaviour fixes:**
  - The briefing asks "How did it go?" once, and the user's answer closes the
    follow-up.
  - Plan saves and ticks happen before the reply, so agents only confirm what
    happened.
  - Plans can be shifted or re-dated, and weekday and heading formats are
    dated.
- **Safety:**
  - Every agent now has a shared crisis rule, with a crisis case in each
    agent's evals.
  - Maddie has urgent-care triage and an eating-disorder response.
- **Infrastructure:** `tzdata` is in the lock with real hashes, and
  `/api/health/detail` now flags a missing timezone database.
- **Privacy notice:** now accurate about what goes to Groq.

The composer now unlocks when the reply ends; memory results follow on the
same stream with their own 30-second clock. The conversation's turn lock is
released once the reply is saved, so the next message never waits for the
previous turn's memory work. Switching conversation mid-reply stops that reply,
and late memory notes only show on the conversation they came from.

Still open from the council:
- database calls still run on the event loop, and memory work is lost if the
  browser disconnects before it finishes (rare now that the page keeps
  listening)
- no global token cap or suspend switch
- screens not built
- RAG plan revised, not started
- the "CrewAi" / CrewAI name clash

## Earlier: keeping track — 2026-09-25 (later)

All nine features from the council review, backend first. They work from chat
and surface through the briefing and the reply notice, with an API for each
(`docs/tracking.md`):

- follow-ups that count down and get asked about once
- saved plans with progress
- check-ins
- a Monday weekly review
- a remaining-allowance figure
- "This is about me:" onboarding
- where each fact came from, with undo
- running summaries for long conversations
- .ics calendar export

Schema **0006**. **406 backend tests.** Screens not built (owner):
plans/follow-ups lists, an "About me" form, the Memory page's source/history/undo
view, and download links for the calendar files.

## Earlier: cost, time, team, memory — 2026-09-25

Four product problems fixed in the backend. No frontend design changes: the
chat screen only sends the browser's timezone and adds text to its existing
"Saved" notice.

- **Cost.** The daily allowance is metered in tokens and trued up to what
  Groq reports. The shared rules went from ~7k to ~3.3k characters, and history
  is capped at 12,000 characters. The memory call is skipped for plain
  questions, and `MEMORY_MODEL` can move it to a smaller model.
  `docs/usage-limits.md`.
- **Time.** Agents get today's date and time in the user's zone. Relative dates
  are resolved, facts store absolute dates, and the briefing counts down to goal
  dates. `docs/agents.md` → Time.
- **Team.** Leo sees recent conversation titles and applies goal changes the
  user explicitly asks for. Any agent can leave a named teammate a note the user
  can see and delete. `docs/agents.md` → Working as a team.
- **Memory.** Keys for the same fact are merged, identical values are not saved
  twice, updates keep the old value in history, and pasted text is never learned
  from. `docs/memory.md`.

Schema **0005**. **386 backend tests.** Not yet run: the live quality evals
against the shorter rules, and any eval of the dated prompt form.

## Earlier: owner decisions implemented — 2026-09-13

Open signup (behind `SIGNUP_ENABLED`, default off) with passwords and single-use
recovery codes; a per-person automatic-memory switch; Ask My Team without
private notes; refunds for provider failures before any text; minimal public
health and agent bodies; sync chat off in production; Next 16 with a per-request
nonce CSP; an automated accessibility scan and keyboard pass. Schema **0004**.
**314 backend tests** (also inside the production image), production rehearsal
**23/23**, 0 frontend advisories. Quality, three samples: partial at **32/36**,
two real grounding lapses. Open: colour contrast (owner), a real screen-reader
pass, a real host and domain, off-host restore, alert delivery, a physical
phone. Details: `launch-fixes.md` → "Owner decisions implemented — 2026-09-13".

## Earlier: review remediation — 2026-09-12

An independent read-only review of the pass below found twelve defects; all the
code findings are fixed with regression tests, plus a latent message-ordering
bug found on the way and a dependency upgrade (FastAPI 0.141.1 / Starlette
1.6.0) that clears 14 published advisories. A second pass over that same work
caught three regressions it had introduced, all fixed. **283 backend tests**,
19/19 production-image browser checks, all application steps of the live journey
on the real model, and a complete release-configuration quality run at
**12/13**. The two measured answer-quality defects were fixed in the shared
prompt rules and re-measured on the live model — neither recurred — but four
samples a case is thin, so a three-sample run remains the next quality
measurement. Details, evidence and the remaining
owner gates: `launch-fixes.md` → "Review remediation — 2026-09-12";
dispositions: `production-readiness-review-2026-09-11.md`.

## Earlier: production-readiness pass — 2026-09-11 (evening)

**Still not approved for public production.** Memory extraction now fails
closed, every reply records how it ended (with an explicit retry), and the
release items — dependency lock, Ask My Team off by default, sustained-failure
readiness, CSP, link policy, API docs off in production — are done. Backend:
**263 tests**, also passing inside the production image. A local rehearsal of the
production images passed 16/16 browser checks with zero CSP violations. The
release-configuration quality run is **incomplete**: the daily quota stopped it
at 27/39 cases (21 passed, 2 failed, 4 ungraded). Details, commands and the
remaining owner-side gates (real domain, off-host restore, scheduler, alert
delivery, physical phone) are in `launch-fixes.md` → "Production-readiness pass".

## Earlier launch-fix pass — 2026-09-11 (historical)

**Not approved for public production.** Read `launch-fixes.md` for current
verification and remaining gates. Account controls and privacy are now in the
frontend; export handles briefing dates; private exception values are removed
from logs; monitoring observes provider failures and recovery; encrypted Linux
backup/restore and failure notifications have been exercised. Shared preferences
now reach specialists through the same filter used by evaluations.

Backend: **154 tests passed**, lint clean. Frontend: production build, typecheck
and lint passed. Nine account browser checks passed with an authenticated mock
backend. Eight Linux operations checks passed using disposable PostgreSQL 16.
These are local checks, not verification of the future host or public domain.

Repeated quality evaluation found answer-quality failures, not just provider
availability problems: configured 120b scored 25/39 with the corrected grader;
the 20b candidate scored 31/39, with 6 failures and 2 unavailable grades. See the current reports and `launch-fixes.md`; older
single-run or keyword-only successes are not a launch sign-off.

---

## Production-readiness pass — 2026-09-10 (historical)

A review for "could this be announced as a product" found gaps that had never
been on the task list, because they only matter once someone other than the
author has a login. Those are now closed.

| Area | State |
|---|---|
| Data export — whole account as JSON, messages included | ✅ `GET /api/users/me/export` |
| Account deletion, including the usage ledger that has no foreign key | ✅ `POST /api/users/me/delete` |
| Single conversation deletion | ✅ `DELETE /api/conversations/{id}` |
| Privacy notice, served by the app and readable before signing up | ✅ `GET /api/legal/privacy` |
| Sign out every device, without signing out everyone else | ✅ `POST /api/auth/sign-out-everywhere` |
| Access-key recovery after loss or leak | ✅ `provision_user.py --rotate` |
| Access log, incident ids, error counters, readiness endpoint | ✅ `GET /api/health/detail` |
| Linux backup + restore-verify scripts, and cron entries for them | ✅ `deploy/*.sh`, `docs/OPERATIONS.md` |
| Recovery point / recovery time stated | ✅ 24h / 1–2h — `docs/OPERATIONS.md` |
| Travel verbosity and invented budgets | ✅ 3/3 clean, 235–305 words |

Backend tests: **130**. Revision **0003** adds the session generation.

### Open

1. **Hosting and domain**, and therefore real-domain TLS. The owner is handling
   this; everything else is finished first by agreement.
2. **A confirming quality run on `openai/gpt-oss-120b`.** Its 200,000/day budget
   was spent repeatedly. Note that `tools.provider_doctor` cannot tell you
   whether a long run will finish — the headers carry the per-minute budget
   only, and the daily one is invisible until exceeded.
3. **The shell backup scripts' encryption and off-host steps have not run on a
   real Linux host** — only their dump/copy/verify steps, from inside a
   container where the bind mount cannot work. Run both by hand once on the host
   before trusting the cron entry.
4. **No high availability.** Single host, single database, no replica. Losing
   the off-host archive and the host together is not survivable. Stated rather
   than solved: a warm standby is a different architecture.

---

## Previous pass — quality, security, deployment prep (2026-09-10)

**Not deployable yet.** Nothing has been published, no host or domain is chosen,
and public-domain HTTPS has not been verified. The container stack was built and run locally in the previous pass. What follows is what is
done, what is verified, and what is still open. Current account-limit and browser results follow below.

### Done and verified

| Area | State |
|---|---|
| Response-quality rubric (`app/agents/rubric.py`) + 32 tests | ✅ Replaces keyword scoring — see `docs/agent-quality.md` |
| Agent prompt fixes (guardrails, Writing, Shopping, Career, Study) | ✅ Deterministic rubric 8/13 → 12/13; different models, not a controlled comparison |
| Live quality run, full responses stored and reviewed | ✅ `docs/live-quality-*.json` |
| Auth on every personal-data route, enforced by a route-table sweep | ✅ `tests/test_auth.py` |
| Ask My Team: anonymous + cross-account regression tests | ✅ New |
| Session expiry, key revocation, foreign-secret cookie, origin checks | ✅ Tested |
| Live end-to-end journey on the real provider, isolated DB | ✅ 12/12 — `backend/journey_check.py` |
| Backend tests · ruff | ✅ 101 passed, lint clean |
| Frontend production build | ✅ Rebuilt, unchanged this pass |
| Container stack: build, migrate, HTTPS, streaming, persistence | ✅ Run end to end locally — see `docs/DEPLOYMENT.md` |
| Backup: retention, AES-256 encryption, off-host copy, restore check | ✅ Executed; archive also decrypts with plain openssl |
| Temporary patch/diagnostic scripts | ✅ Removed or folded into `backend/tools/` |

### Fixed this pass, worth knowing

- **`chat/stream` answered 422 before 401.** Auth ran inside the handler, after
  body validation, so an anonymous caller learned the request schema. Auth is now
  a FastAPI dependency (`core.auth.caller_id`) on both chat routes and Ask My
  Team. A test walks the real route table so a new endpoint cannot skip it.
- **Rate limits were being recorded as bad answers.** Two earlier quality runs
  had empty replies scored as quality failures; they were 429s. The eval harness
  now backs off and retries, and tells a per-minute throttle apart from a daily
  quota (`ProviderError.retry_after`) so it aborts instead of burning a run.
- **An aborted run destroyed the previous results file.** It now writes to
  `<out>.partial` and promotes only on completion.

### Still open

1. ~~11 of 13 cases unconfirmed on `openai/gpt-oss-120b`.~~ **Done, and it
   changed the picture** — see `docs/agent-quality.md`. The baseline run
   completed 12 of 13 cases and scored **7/12**, not the 12/13 measured on
   `qwen3.8-27b`; the qwen number was flattering because the prompts had been
   tuned against it. The exposed defects are fixed and re-verified clean on
   `gpt-oss-20b` (18/18, then 8/8). **A confirming pass of those fixes on
   `gpt-oss-120b` is still outstanding** — the daily budget ran out.
2. ~~Eval variance is large and unmeasured.~~ **Done.** `quality_check.py` takes
   `--samples`, `--resume` and an evaluation-only `--model`, and reports per-case
   pass rates that separate provider outages from real quality failures.
3. **Travel is the one agent still failing.** On the production model it ran to
   521 words against a 450 ceiling, and on one sample invented a budget and
   attributed it to the user ("You're comfortable with a moderate budget").
   Improved from the previous round, not closed.
4. **The LLM judge is only as good as the judge model.** With `qwen3.8-27b`
   judging, `currency` and `grounding` fired on column headers, hedged figures,
   and examples the reply itself labelled "Example". Both dimensions have been
   rewritten to list what passes. Use the strongest available model, and read the
   quoted evidence rather than the score.
5. **`--model` overrides every agent, including Writing's own `qwen3.8-27b`.**
   Writing "failed" three runs on a model it never uses; on its production
   configuration it passes 2/2. Check what an agent actually runs on before
   believing a verdict about it.
6. **TLS for a real domain is untested.** The local run used `DOMAIN=localhost`,
   which makes Caddy use its internal CA; Let's Encrypt needs a public hostname,
   so certificate issuance can only be proven on the real host. Restoring over a
   **populated** database is now rehearsed and passing, including the usage
   ledger.
5. **Public hosting and operational activation remain open.** Choose a host/domain, verify public HTTPS, schedule backups and monitoring, and decide how to merge the hardening branch.

## Account limits and browser pass — 2026-09-10

- Durable per-account limits now cover chat, streamed chat, every team specialist, synthesis, and LLM memory extraction. Defaults: 6 requests per fixed minute, 60,000 conservative token-budget units per UTC day. See [usage-limits.md](usage-limits.md).
- Limits use authenticated identity, atomic database updates, and survive process restarts. Failed/interrupted model calls stay charged. Background extraction falls back to rules if its budget is exhausted.
- Browser displays the server's rate-limit explanation instead of a generic HTTP error.
- Backend: 112 tests pass; ruff clean. SQLite and PostgreSQL 16 migration upgrade/downgrade/upgrade executed. PostgreSQL concurrent admission and fresh-process persistence passed. Frontend build, lint and typecheck passed.
- Browser: 13 mock journey checks and 3 live mobile checks passed. Results and limitations: see [browser-qa.md](browser-qa.md). The original live provider journey and container/backup checks above belong to the previous pass.
- The generated character artwork and approved comic design are unchanged.

Historical design-phase notes are [archived](archive/design-status-2026-09-09.md); their old artwork descriptions, test counts and paid-tier advice are superseded.
