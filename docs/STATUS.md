# Project status — Modeer Personal AI Team MVP

_Last updated: 2026-09-09 · commit `d831c73`_

---

## 1. Where the project is

The repository is fully initialized and the **first milestone works end to end**.
Backend and frontend both build, all tests pass, and the core flow (Modeer learns
a fact → specialists use it → memory is editable) is verified over real HTTP.

| Area | State |
|---|---|
| Repo scaffold (backend, frontend, docs, docker-compose, env templates) | ✅ Done |
| Database models + migration | ✅ Done (8 tables, Alembic `0001`, up/down verified) |
| Agent runtime + registry + 10 agent configs/prompts | ✅ Done |
| Two-layer memory + extraction + isolation | ✅ Done |
| LLM provider abstraction (mock + Anthropic streaming) | ✅ Done |
| API (health, users, agents, conversations, chat, memory, goals, briefings, team) | ✅ Done |
| Frontend (Home, Team, Agent workspace, Memory, Goals) + streaming | ✅ Done |
| Tests (50 pytest, all green) + agent eval fixtures | ✅ Done |
| Docs (README, product, architecture, agents, memory) | ✅ Done |
| **Real LLM responses** | ⏳ Needs your API key |
| **Visual/browser QA of the UI** | ⏳ Needs you (browser tools were off) |
| **Prompt tuning against a real model** | ⏳ Needs you + a key |

---

## 2. What is done (detail)

### Backend — `backend/`
- **FastAPI modular monolith.** One app, one DB, one LLM provider, one agent
  runtime. No microservices, no agent frameworks (LangChain/CrewAI/etc.), no
  tools, no MCP — matching the brief's exclusions.
- **Agent runtime** (`app/agents/runtime.py`): persist user message → load agent
  config → load shared context + agent memory + goals → load conversation
  history → build context packet → stream from LLM → persist reply →
  extract candidate memories. Every agent (Modeer + 9 specialists) runs through
  this; agents are **configuration, not code**.
- **Agent configs** in `app/agents/<slug>/`: `config.py` (identity, expertise,
  explicit `reasoning_framework`, `response_behavior`, `safety_boundaries`,
  model settings) + `prompt.md` (versioned system instructions) + `evals.json`
  (7 test categories). All 10: modeer, study, travel, shopping, career, finance,
  fitness, writing, research, email.
- **Each specialist has a real domain reasoning framework** (internal, never
  echoed to the user), not a "you are an expert X" flavour line.
- **Memory:** shared personal context (team-wide, filtered per agent by the
  agent's `shared_context_fields`) + per-agent private namespaces. Extraction is
  deterministic/rule-based and conservative — temporary details are dropped,
  sensitive data (health, salary, IDs) is flagged and **not** stored unless you
  opt in via `MEMORY_STORE_SENSITIVE=true`.
- **LLM:** `app/llm/` — `base.py` (interface), `mock_provider.py`
  (context-aware, no key, used by all tests), `anthropic_provider.py` (streaming
  Claude Messages API), `provider.py` (factory). Swap providers by editing one
  file. No model routing.
- **DB models** (`app/db/models.py`): `users, agents, conversations, messages,
  shared_memories, agent_memories, goals, briefings` — FKs, indexes,
  timezone-aware timestamps, string-UUID PKs (portable SQLite↔Postgres).
  Alembic migration `0001_initial_schema.py`.
- **API** (`/api/…`): health · users/me · agents · conversations · chat (SSE
  stream + non-streaming fallback) · memory (shared + agent CRUD) · goals CRUD ·
  briefings/today · team/ask (explicit "Ask My Team" consult).
- **Daily briefing:** built only from stored goals + shared context. Never
  claims external facts (calendar, email, weather).
- **Tests:** 50 `pytest` cases — registry, config loading, context construction,
  memory isolation (per-user **and** per-agent), shared-memory behaviour,
  conversation persistence, user isolation, API surface, and the full milestone
  flow (`tests/test_milestone_flow.py`). LLM mocked throughout. `ruff` clean.
- **Evals:** `python -m app.agents.evals` — every agent has cases for in-domain,
  ambiguous, out-of-domain, personalization, bad-assumption, safety, quality.

### Frontend — `frontend/`
- Next.js 15 (App Router) + React 19 + TypeScript + Tailwind. `npm run build`,
  `lint`, `typecheck` all clean.
- **Screens:**
  - **Home** — greeting, Modeer daily briefing card, "Talk to Modeer" CTA, AI
    Team grid, current goals.
  - **AI Team** — Modeer + all 9 specialists; each card has icon, accent
    colour, role, description. Pick one directly.
  - **Agent workspace** (`/agents/[id]`) — specialist identity header, streaming
    chat, conversation rail (independent histories per agent), a subtle note
    when personal context informed a reply, "saved to your context" confirmation.
  - **Memory** (`/memory`) — "What my AI team knows about me": view / add /
    edit / delete shared memories and per-specialist notes.
  - **Goals** (`/goals`) — create, prioritise, complete, delete.
- SSE streaming hook (`features/chat/useChatStream.ts`). `/api/*` is proxied to
  the backend in dev, so there is **no CORS setup** to do.
- Design is a dark "command center" with per-agent accents — deliberately not a
  ChatGPT-with-a-sidebar clone.

### Verified working (over real HTTP, not just unit tests)
1. Talk to Modeer, share "I'm studying mechanical engineering… want to be a
   robotics engineer" → both facts saved to shared context.
2. Open **Career Agent** directly → it already knows field + goal.
3. Open **Study Agent** directly → uses the same field for its domain.
4. Career and Study keep **separate** conversation histories.
5. SSE streaming emits `start` / `delta` / `end` events.
6. Edit a memory → returns updated value. Delete → `204`.
7. Ask My Team with `["career","study"]` → both answer + Modeer synthesises.

---

## 3. What you need to do

### A. To run it locally (required — one-time, ~5 min)

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate                 # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
uvicorn app.main:app --reload          # http://localhost:8000  (API docs at /docs)

# 2. Frontend (second terminal)
cd frontend
npm install
copy .env.example .env.local
npm run dev                            # http://localhost:3000
```

The backend uses **SQLite by default** — nothing else to install. It works fully
on the mock LLM (responses are placeholders that echo your context, so you can
see personalization and memory working without a key).

> Note: `.venv` and `node_modules` already exist locally from this session, so
> `pip install` / `npm install` will be quick or can be skipped.

### B. To get real AI responses (your Anthropic API key)

Edit `backend/.env`:

```env
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...        # <-- your key
LLM_MODEL=claude-sonnet-5     # or another Claude model
```

Restart the backend. That's the only secret the project needs. **Do not commit
`.env`** (it's git-ignored).

### C. To use PostgreSQL instead of SQLite (optional)

```bash
docker compose up -d db       # Postgres on :5432, user/pass/db all "modeer"
```

Set in `backend/.env`:
```env
DATABASE_URL=postgresql+psycopg://modeer:modeer@localhost:5432/modeer
```
Then: `cd backend && alembic upgrade head`.

### D. Decisions and review that need a human

| # | What | Why it needs you |
|---|---|---|
| 1 | **Visual QA of the UI** in a browser | Browser tools were disabled this session. Click through all 5 screens on desktop + mobile widths; check the streaming chat feel, accent colours, empty states. |
| 2 | **Prompt tuning against a real model** | Prompts are strong drafts written without a live model. Run `LLM_PROVIDER=anthropic … python -m app.agents.evals` and iterate on `app/agents/<slug>/prompt.md` where answers miss. |
| 3 | **Auth strategy** | MVP ships a single local "demo user" (an `X-User-Id` header for tests). Decide if/when you want real accounts before multi-user use. |
| 4 | **Which 4 agents stay lighter** | Brief said prioritise Modeer/Study/Career/Research/Writing. All 9 are implemented on the same runtime, but Travel/Shopping/Finance/Fitness/Email prompts have had less iteration — decide how deep to go. |
| 5 | **Deployment target** | No hosting/CI is set up (out of scope for the MVP). Decide where this runs when you're ready. |
| 6 | **Model id sanity-check** | `LLM_MODEL` defaults to `claude-sonnet-5`; confirm the exact model string you want to bill against. |

---

## 4. Not built yet (beyond the milestone — your call on priority)

These were explicitly deferred by the brief or are natural next steps:

- **"Ask My Team" polish.** A minimal explicit endpoint exists
  (`POST /api/team/ask`) and is tested, but there's no frontend screen for it
  yet. Brief said not to prioritise this before core chat is stable — it now is.
- **Onboarding flow.** Modeer's prompt handles onboarding conversationally, but
  there's no dedicated first-run wizard / profile-setup UI.
- **LLM-assisted memory extraction.** Current extraction is rule-based
  (deterministic, safe, testable). A real model could catch more nuanced facts —
  add it behind the existing `extract_candidates` seam if wanted.
- **Briefing scheduling / history view.** Briefings are generated on request and
  stored per day; there's no "past briefings" screen.
- **Auth, rate limiting, observability, CI/CD** — not part of the MVP scope.
- **Eval scoring against a rubric model** (LLM-as-judge). Harness is ready; only
  heuristic scoring runs today.

---

## 5. Known limitations / tech debt

- **Mock LLM output is intentionally plain** — it echoes injected context to
  prove the pipeline. Real quality needs a key (section 3B).
- **`next lint`** prints a deprecation notice (still works; Next 16 will remove
  it). Migrate to the ESLint CLI eventually.
- **SQLite on Windows** holds the DB file open until `engine.dispose()` — handled
  in tests; only relevant if you script DB teardown.
- **No pagination** on conversation / memory / goal lists (fine at MVP scale).
- Agent prompts and `evals.json` expectations are first drafts — see 3D#2.

---

## 6. Quick reference

| Task | Command (from the folder shown) |
|---|---|
| Run backend | `backend/` → `uvicorn app.main:app --reload` |
| Run frontend | `frontend/` → `npm run dev` |
| Backend tests | `backend/` → `python -m pytest -q` |
| Backend lint | `backend/` → `ruff check .` |
| Agent evals | `backend/` → `python -m app.agents.evals` |
| Frontend checks | `frontend/` → `npm run build` / `npm run lint` / `npm run typecheck` |
| DB migrate (Postgres) | `backend/` → `alembic upgrade head` |
| Start Postgres | repo root → `docker compose up -d db` |

More detail: `README.md`, `docs/product.md`, `docs/architecture.md`,
`docs/agents.md`, `docs/memory.md`.
