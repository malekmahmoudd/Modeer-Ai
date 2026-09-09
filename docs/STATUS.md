# Project status — Modeer Personal AI Team MVP

_Last updated: 2026-09-09 · phase: UI/UX + agent-quality polish_

---

## 1. Where the project is

MVP core is complete and the **first milestone works end to end on the real
model**. This pass focused on the two stated priorities — **UI/UX quality** and
**specialist-agent performance** — plus making shared personal context actually
feel intelligent.

| Area | State |
|---|---|
| Repo scaffold · DB models + migration · API · docs | ✅ Done |
| Agent runtime + registry + 10 agent configs/prompts | ✅ Done |
| **Real LLM provider wired (Groq / OpenAI-compatible)** | ✅ Done — streaming, 429 back-off |
| **LLM-assisted memory extraction** (rules fallback) | ✅ Done |
| **Frontend redesign** — new design system, all 5 screens | ✅ Done |
| **First-run onboarding** ("Meet Modeer" → chat → team) | ✅ Done |
| Agent prompt improvements (Modeer, Career, Research + global) | ✅ Done |
| Tests (58 pytest) · ruff · tsc · next build · next lint | ✅ All green |
| Priority-5 agent evals on the real model | ✅ 31/35 (89%) baseline; re-run after fixes |
| **Visual/interaction QA in a real browser** | ⛔ Blocked — needs you (browser tools were off this session) |
| Remaining-5 agents: full eval sweep on real model | ⏳ Rate-limited; spot-checked OK |

---

## 2. What changed this pass

### Phase 1 — Real model
- Added `LLM_PROVIDER=groq` / `openai` support: a single OpenAI-compatible
  streaming provider (`app/llm/openai_compat_provider.py`) with **429 rate-limit
  back-off** (honours `retry-after` / "try again in Ns"). Your `.env` was pointing
  at Groq `openai/gpt-oss-120b`; that now works.
- **Security fix:** your Groq key was in `backend/.env.example` (a git-tracked
  template — though not yet committed). Moved it to `backend/.env` (git-ignored)
  and restored the template to placeholders. **Rotate that key** — it was shared
  in plaintext. See §4.
- Streaming, context injection, Modeer, specialists and memory all verified
  against the real model over HTTP.
- Eval harness: added `--delay` (throttle) and `--show`; per-case failures no
  longer abort the run.

### Phase 3 — Agent performance (real-model eval: 31/35 on the priority 5)
Fixed the real problems the eval surfaced:
- **Modeer** now hands off clearly when a request is squarely a specialist's job
  ("the Fitness Assistant is built for this — want to take it there?"), instead
  of quietly doing the specialist's whole job.
- **Career** — a refusal to fabricate credentials now *pivots* to the honest move
  (reframe real experience, quantify impact) instead of a bare "I can't help."
- **Research** — states up front it can't pull/verify live sources and won't
  invent citations, then stays useful (what to search, where).
- **Global guardrail** (all agents): personal context is background, not a
  checklist — use a fact only when it changes the answer; never open with a
  recap of what you know. (Phase 4.)
- Two eval cases were harness false-negatives (a correct JARVIS refusal, a
  correct citation refusal) — expectations corrected.
- Spot-checked Fitness / Finance / Email on the real model: each shows its
  domain framework (Fitness asks background + injuries first; Finance leads with
  "education, not advice"; Email is BLUF with a subject line). Not shallow.

### Phase 4 — Context & memory quality
- **LLM-assisted extraction** (`app/memory/llm_extraction.py`): when a real
  provider is set, one short JSON call per user message proposes durable facts;
  the **same conservative gates** as the rule-based path then decide what's
  stored (sensitive dropped unless opted in, low-confidence dropped, agent-scoped
  facts kept only in-domain). Falls back to rules on any bad output. Rules still
  run for `mock` / tests, so the suite stays deterministic.
  - Before: "I'm a third-year CS student at Cairo University, goal is an ML
    internship next summer" → 2 poor facts (`level = "computer science"`).
  - After: 5 clean facts — field of study, year, institution, inferred location,
    and the ML-internship **goal**; powerlifting "4×/week" routed to the Fitness
    agent's private notes; "my salary is …" + "diagnosed with asthma" flagged
    sensitive and **not stored**.
- 8 new deterministic tests (`tests/test_llm_extraction.py`) cover parsing,
  gates, scope routing and fallback.
- Runtime now emits `end` (answer done) then a trailing `memory` event, so the
  reply renders instantly and the "saved to your context" confirmation follows.

### Phase 5 — First-run experience
- New users land on **"Meet Modeer"** (not a form): one line of context → "Start
  with Modeer" → a guided first message. Onboarding completes itself once Modeer
  has learned ~3 durable facts (or after a few exchanges with ≥1 fact), and the
  workspace shows a "Your team is set up" banner linking to the team.

### Phase 2 / UI — full redesign
New token-based design system (`globals.css` + `tailwind.config.ts`): calmer
near-black palette, one subtle ambient wash (no gradient soup), hairline borders
used sparingly, a real type/spacing/radius scale, restrained motion
(`prefers-reduced-motion` respected), inline SVG icon set.

- **Home** — greeting by name; **Modeer hero panel** (distinct from the grid) with
  the daily briefing as tappable rows tinted by the related specialist's accent,
  an inline "Message Modeer…" composer, and an active-goals chip. Below: the team
  as one-line roster cards (name · tagline · accent — no paragraphs).
- **Team** — Modeer as a wide feature row, then the nine specialists.
- **Agent workspace** — clean identity header with a per-agent accent hairline,
  agent-specific empty-state question + starter chips, agent-specific composer
  placeholder, auto-growing composer, a small "Personalized from your saved
  context" link (no token counts / model names / internals), desktop conversation
  rail + mobile history sheet. A proper markdown renderer (headings, lists,
  tables, code, quotes) replaces the previous naive one.
- **Memory** — "Shared with your team" grouped by human category; "Known by
  specific agents" behind an accent-chip picker; rows read as labelled facts, not
  raw key/value; inline add / edit / delete; a trust line about sensitive data.
- **Goals** — restyled, still lightweight (no kanban/dependencies).
- **Nav** — slim left rail on desktop (no promo clutter), **bottom tab bar** on
  mobile. Presentation fields (`tagline`, `composer_placeholder`, `empty_prompt`,
  `starters`) live in each agent's `config.py`, served by the API — the UI stays
  config-driven.

---

## 3. What you need to do

### A. Rotate the Groq API key (do this)
`gsk_…` was pasted into a tracked template file and into this session in
plaintext. It's now only in the git-ignored `backend/.env`, but treat it as
exposed: revoke it at <https://console.groq.com/keys>, create a new one, and put
it in `backend/.env` (never `.env.example`).

### B. Run it
```bash
# backend  (venv + deps already installed locally)
cd backend && .venv\Scripts\activate
uvicorn app.main:app --reload            # :8000

# frontend
cd frontend && npm run dev               # :3000
```
`backend/.env` already has your Groq config. SQLite is the default DB — no setup.
If the Next dev server ever 500s with "Cannot find module './xxx.js'", stop it,
`rm -rf frontend/.next`, and restart (stale dev cache, not a code bug).

### C. Visual + interaction QA — the main open item
Browser tools were disabled this session, so the redesign was verified by
`next build` / `tsc` / `next lint` and by driving every flow over HTTP — **not by
looking at it**. Please walk through, at desktop / laptop / tablet / mobile
widths:
- Home (onboarded and not), Team, a couple of specialist chats, Memory, Goals.
- Streaming feel, the accent-hairline identity cue per agent, empty states,
  the mobile bottom nav + history sheet, composer on a phone keyboard.
Note anything that feels off; it's fast to iterate from a concrete list.
(`/chrome` in Claude Code enables browser tools if you want me to do this pass.)

### D. Decisions still yours
| # | What | Why it needs you |
|---|---|---|
| 1 | Groq free tier is ~8k tokens/min | Fine for use; the full 70-case eval sweep gets rate-limited. Consider a paid tier or a second key for CI-style eval runs. |
| 2 | Auth strategy | Still a single local "demo user". Decide before multi-user. |
| 3 | Model choice | `openai/gpt-oss-120b` is solid in testing. Confirm it's what you want, or switch `LLM_MODEL`. |
| 4 | Deployment target | No hosting/CI yet (out of MVP scope). |

---

## 4. Known limitations / tech debt

- **Not visually reviewed** (see §3C) — the single biggest open item.
- **Remaining-5 agents**: only spot-checked on the real model; the full eval
  sweep was rate-limited. Re-run `python -m app.agents.evals travel shopping
  finance fitness email --delay 22` when the budget allows.
- **LLM extraction adds one short model call per user message** (after the reply
  streams, so no perceived latency). Set `MEMORY_EXTRACTION=rules` to disable.
- `next lint` prints a deprecation notice (works; Next 16 removes it).
- The markdown renderer is deliberately small — handles the common cases
  (headings, lists, tables, code, quotes, bold/italic/links), not full CommonMark.
- No pagination on conversation / memory / goal lists (fine at MVP scale).

---

## 5. Suggested next phase

1. **Do the visual QA pass** (§3C) and fix the concrete list it produces.
2. **Finish the real-model eval sweep** for all 10 agents; iterate on any prompt
   below ~80%.
3. **"Ask My Team" front end** — the API (`POST /api/team/ask`) and synthesis
   exist; there's no screen yet. This is the natural next feature once UI/UX and
   agent quality are signed off.
4. Optional: briefing history view; a real profile/settings screen; auth.

Do not start #3 before #1–#2 are done.

---

## 6. Quick reference

| Task | Command (from the folder shown) |
|---|---|
| Run backend / frontend | `uvicorn app.main:app --reload` / `npm run dev` |
| Backend tests / lint | `python -m pytest -q` / `ruff check .` |
| Frontend checks | `npm run build` · `npm run lint` · `npm run typecheck` |
| Agent evals (real model) | `python -m app.agents.evals <slugs> --delay 22 --show` |
| Force rule-based memory | `MEMORY_EXTRACTION=rules` in `backend/.env` |
| DB migrate (Postgres) | `alembic upgrade head` |

More detail: `README.md`, `docs/{product,architecture,agents,memory}.md`.
