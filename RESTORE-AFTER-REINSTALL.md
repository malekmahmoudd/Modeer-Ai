# Restore Fareeq after reinstalling macOS

Updated 30 September 2026. The complete release work is on
**`codex/staging-readiness`**, not the repository's older default branch.

## Get the project

Install Git, Python 3.12 and Node.js 22 on the fresh Mac, then:

```sh
git clone --branch codex/staging-readiness https://github.com/malekmahmoudd/Modeer-Ai.git
cd Modeer-Ai
```

Open this folder in your editor or Codex. The repository includes source code,
agent prompts, migrations, tests, artwork and documentation, including
`docs/Fareeq-AI-New-Features.docx`. That document is a historical snapshot;
its statement that the review fixes are uncommitted is now outdated.

## Start locally with a new empty database

No hosting account, billing details or API key is needed for mock mode.
In one terminal, from the repository root:

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL='sqlite+pysqlite:///./modeer.db'
export LLM_PROVIDER=mock
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1
```

Run migrations **before** starting the app, including for a fresh SQLite
installation. Do not run this fresh-database procedure over an old database
without first following the restore/migration runbooks.

In another terminal, from the repository root:

```sh
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. This is a local mock setup; real AI, transcription,
OCR dependencies and semantic document search need their additional setup.
See README.md and docs/rag.md. Recreate configuration with newly issued keys
when enabling real providers; never put keys in frontend variables or Git.

## What GitHub does not contain

- Local SQLite databases, conversations, memories and account records.
- Private database backups and the ignored `backups/` folder.
- Real `.env` files, API keys, account credentials or browser-stored drafts.
- Installed dependencies, downloaded models, build caches or local QA screenshots.
- Codex chat history or other files outside this repository.

If the local data matters, keep a separate encrypted backup on trusted storage
before erasing the Mac. A Git clone cannot recover those excluded files.
Dependencies and models can be installed/downloaded again.

Because the old laptop was reported compromised, use a trusted device to revoke
old GitHub/provider sessions and credentials and issue replacements. Do not
restore old credentials or executable environments from the compromised system.

## Deployment status and constraints

**No billing details and no credit card are permitted.** No staging or production
service was deployed. Render's Blueprint setup requested payment information,
so that route was stopped. `render.yaml` and `docs/STAGING-RENDER.md` are retained
as prepared configuration, not evidence of a live deployment or a usable
no-card hosting option. Do not continue the Render billing flow.

Production domain: `fareeq.io`. Hosting without a card, real-device checks and
other remaining launch gates still need completion. See docs/ROLLOUT-0013.md.
