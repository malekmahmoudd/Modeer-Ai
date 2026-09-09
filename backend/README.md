# Modeer backend

FastAPI modular monolith. See the repo root [`README.md`](../README.md) and
[`docs/`](../docs) for the full picture.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Unix: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

alembic upgrade head          # only needed for PostgreSQL; SQLite auto-creates
uvicorn app.main:app --reload # http://localhost:8000  ·  docs at /docs
```

## Common commands

```bash
pytest                        # full suite, LLM mocked
ruff check .                  # lint
python -m app.agents.evals    # agent evaluation harness
alembic revision -m "msg"     # new migration (autogenerate needs a live DB)
```

## Layout

```
app/
  main.py            app + lifespan
  core/config.py     settings
  db/                Base, session, models
  api/routes/        health users agents conversations chat memory goals briefings team
  agents/            schema · registry · context · runtime · evals · <slug>/*
  llm/               base · mock · anthropic · provider
  users/ conversations/ memory/ goals/ briefings/   schemas + services
migrations/           Alembic (0001 = full initial schema)
tests/                registry, context, memory isolation, API, milestone flow
```
