# Modeer — Personal AI Team (MVP)

A personal AI assistant, **Modeer**, plus a user-chosen team of nine specialist
AI agents that share your personal context.

You open the app, see your team, and talk to whoever you want — directly. You do
**not** have to go through Modeer to reach a specialist. Modeer is the assistant
that learns you, keeps the shared context the whole team draws on, tracks your
goals, and gives you a daily read on what matters.

| Specialists |
|---|
| Study · Travel · Shopping · Career · Finance · Fitness · Writing · Research · Email |

The three priorities, in order: **excellent UI/UX**, **excellent specialist
performance**, **shared personal context that makes the whole team feel like it
knows you**.

---

## Architecture at a glance

```
frontend/   Next.js (App Router) + React + TypeScript + Tailwind
backend/    FastAPI modular monolith — one shared agent runtime, not a service per agent
            Python · Pydantic · SQLAlchemy · Alembic · PostgreSQL
docs/       product, architecture, agents, memory
```

- **One agent runtime.** Every agent (Modeer + nine specialists) is a
  *configuration* — `backend/app/agents/<slug>/{config.py,prompt.md,evals.json}` —
  run through the same `runtime.py`. No LangChain / LangGraph / CrewAI, no tools,
  no browsing, no autonomous actions.
- **Two memory layers.** Shared personal context (whole team) and agent-specific
  memory (one specialist's namespace). Extraction is deterministic and
  conservative; sensitive data is never stored automatically.
- **One LLM provider** behind a thin abstraction (`app/llm/`). Ships with a
  context-aware **mock** provider so the whole product runs with no API key;
  set `LLM_PROVIDER=anthropic` for real responses. Streaming throughout.

See [`docs/architecture.md`](docs/architecture.md) for the full picture and
[`docs/agents.md`](docs/agents.md) for how each specialist is designed.

---

## Local development

Prerequisites: **Python 3.11+**, **Node 20+**, and (optionally) **Docker** for
PostgreSQL. The backend falls back to SQLite with zero configuration, so you can
skip Docker entirely for a first run.

### 1. Database (optional but recommended)

```bash
docker compose up -d db      # PostgreSQL on localhost:5432 (user/pass/db = modeer)
```

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows:        .venv\Scripts\activate
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements-dev.txt      # or requirements.txt for runtime only

cp .env.example .env                      # then edit if you want Postgres / a real LLM

# With PostgreSQL (DATABASE_URL set in .env):
alembic upgrade head

uvicorn app.main:app --reload             # http://localhost:8000  (docs at /docs)
```

> Using the SQLite default? Skip `alembic upgrade head` — the schema is created
> automatically on first start. To use Alembic against SQLite anyway, it works too.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                               # http://localhost:3000
```

The frontend proxies `/api/*` to the backend (`BACKEND_URL`, default
`http://localhost:8000`), so no CORS setup is needed for local dev.

---

## Environment variables

### `backend/.env`

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite+pysqlite:///./modeer.db` | Use `postgresql+psycopg://modeer:modeer@localhost:5432/modeer` for the real stack |
| `ENVIRONMENT` | `development` | |
| `FRONTEND_URL` | `http://localhost:3000` | CORS allow-list (comma-separated) |
| `LLM_PROVIDER` | `mock` | `mock`, `anthropic`, `groq`, or `openai` |
| `LLM_API_KEY` | _(empty)_ | Required for any real provider |
| `LLM_MODEL` | `claude-sonnet-5` | e.g. `openai/gpt-oss-120b` for Groq |
| `LLM_BASE_URL` | _(empty)_ | Override the provider base URL (groq/openai) |
| `LLM_MAX_TOKENS` / `LLM_TEMPERATURE` | `1024` / `0.6` | Per-agent settings can override |
| `MEMORY_EXTRACTION` | `auto` | `auto` (LLM when a real provider is set), `llm`, `rules` |
| `MEMORY_STORE_SENSITIVE` | `false` | Keep sensitive candidates out of storage |
| `MEMORY_MIN_CONFIDENCE` | `0.55` | Extraction threshold |

### `frontend/.env.local`

| Variable | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `/api` | Where the browser sends API calls |
| `BACKEND_URL` | `http://localhost:8000` | Origin the dev server proxies `/api/*` to |

No real API keys are committed. `.env` files are git-ignored.

---

## Migrations

```bash
cd backend
alembic upgrade head                       # apply
alembic downgrade -1                        # roll back one
alembic revision -m "add x"                 # new migration (autogenerate needs a live DB)
```

Migrations live in `backend/migrations/versions/`. `0001_initial_schema.py`
creates all tables: `users, agents, conversations, messages, shared_memories,
agent_memories, goals, briefings`.

---

## Testing & evaluation

```bash
cd backend
pytest                                      # deterministic; LLM calls mocked
ruff check .                                 # lint

python -m app.agents.evals                   # agent eval fixtures (mock provider)
python -m app.agents.evals study career       # a subset
LLM_PROVIDER=anthropic LLM_API_KEY=... python -m app.agents.evals   # qualitative pass
```

```bash
cd frontend
npm run typecheck
npm run lint
```

Tests cover the agent registry, config loading, context construction, memory
isolation (per user **and** per agent), shared-memory behaviour, conversation
persistence, the API surface, and the full first-milestone flow end to end
(`tests/test_milestone_flow.py`).

---

## The first milestone

1. Open the app → talk to **Modeer**, share a durable fact ("I'm studying
   mechanical engineering…").
2. It lands in **shared personal context**.
3. Go back to the team, open **Career Agent** directly — it already knows.
4. Open **Study Agent** — it uses the same fact for its own domain.
5. Both keep independent conversation histories.
6. Open **"What my AI team knows about me"** and edit or delete the fact.

This flow is exercised by `pytest` and is the thing to keep excellent.
