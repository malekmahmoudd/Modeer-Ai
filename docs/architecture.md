# Architecture

## Shape

A **modular monolith**. One FastAPI app, one PostgreSQL database, one LLM
provider, one agent runtime. No service per agent, no message bus, no
orchestration framework.

```
backend/app/
├── main.py            FastAPI app + lifespan (schema on SQLite, agent-table sync)
├── core/config.py     settings (pydantic-settings, .env)
├── db/                Base, session, models (all ORM models in models.py)
├── api/               deps + routers (health, users, agents, conversations,
│                      chat, memory, goals, briefings, team)
├── agents/
│   ├── schema.py      AgentConfig (typed)
│   ├── registry.py    discovers app/agents/<slug>/config.py + prompt.md
│   ├── context.py     builds the context packet for one turn
│   ├── runtime.py     the single shared runtime
│   ├── evals.py       eval harness (fixtures in <slug>/evals.json)
│   └── <slug>/        config.py · prompt.md · evals.json   (x10)
├── llm/               base (interface) · mock · anthropic · provider (factory)
├── users/ conversations/ memory/ goals/ briefings/   (schemas + services)
└── migrations/        Alembic
```

## Request → response (one chat turn)

```
POST /api/agents/{slug}/chat/stream
        │
        ▼
resolve user (X-User-Id header or demo user)
get-or-create conversation for (user, agent)
        │
        ▼  AgentRuntime.run_stream
persist user message
load AgentConfig (registry)
load shared personal context  ── filtered by agent.shared_context_fields
load agent-specific memory     ── namespace = agent slug
load conversation history      ── this conversation only
build context packet           ── system prompt + framework + guardrails +
                                  <<PERSONAL_CONTEXT>> + <<AGENT_MEMORY>> + goals
        │
        ▼
LLMProvider.stream_chat  ──►  SSE: {type:"start"|"delta"|"end"|"error"}
        │
        ▼
persist assistant message (+ context diagnostics in meta)
extract candidate memories from the user message → apply the storable ones
emit "end" with memory_candidates + context_used
```

`POST /api/agents/{slug}/chat` is the same pipeline, non-streaming, for tests and
as a fallback.

## Agents are configuration

An agent is `AgentConfig` (identity, expertise, `reasoning_framework`,
`response_behavior`, `safety_boundaries`, `model`) plus `prompt.md`. The registry
loads them at import and caches. The `agents` DB table is a mirror kept in sync
on startup for FK integrity; **code is the source of truth**.

Adding an agent = a new `app/agents/<slug>/` folder. No API, runtime, or schema
changes.

## LLM provider

`LLMProvider.stream_chat(...)` is the whole interface. `provider.py` picks one
implementation from `LLM_PROVIDER`:

- `mock` (default) — deterministic, context-aware placeholder; no key; used in
  all automated tests.
- `anthropic` — Claude Messages API, streamed over httpx.

No model routing, no multi-provider fan-out.

## Persistence

SQLAlchemy 2.0 typed models, string UUID PKs (portable across SQLite/Postgres),
timezone-aware timestamps, `JSON` columns (not `JSONB`) for portability. Indexes
on every foreign key and the common `(user_id, …)` lookups. Alembic migration
`0001` creates the full schema.

`DATABASE_URL` defaults to SQLite so the app runs with zero setup; PostgreSQL via
`docker compose up -d db` is the intended target.

## Frontend

Next.js App Router, all pages client components (the backend has no auth/SSR
concerns). `lib/api.ts` wraps fetch + a tiny `useApi` hook; `features/chat/
useChatStream.ts` parses the SSE stream into React state. `/api/*` is proxied to
the backend by `next.config.mjs`, so no CORS setup locally.

## Isolation guarantees (tested)

- A user only ever sees their own conversations, memories, goals, briefings.
- A specialist sees shared context + its own namespace — never another agent's
  memory or transcript.
- Memory extraction never stores sensitive candidates automatically.
