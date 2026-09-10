# Project status — Modeer Personal AI Team MVP

_Last updated: 2026-09-10 · phase: hardening for a private, invite-only deployment_

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
