# Modeer frontend

Next.js (App Router) + React + TypeScript + Tailwind. See the repo root
[`README.md`](../README.md) for the full picture.

## Quick start

```bash
npm install
cp .env.example .env.local
npm run dev        # http://localhost:3000  (needs the backend on :8000)
```

`/api/*` is proxied to `BACKEND_URL` (default `http://localhost:8000`) by
`next.config.mjs`, so there's no CORS setup for local dev.

## Commands

```bash
npm run dev        npm run build        npm run start
npm run lint       npm run typecheck
```

## Layout

```
src/
  app/                    layout · page (Home) · team · agents/[agentId] · memory · goals
  components/
    AppShell · AgentCard · AgentGrid · AgentAvatar · BriefingCard · GoalsPanel
    chat/     ChatWorkspace · MessageBubble
    memory/   MemoryManager · MemoryRow
    goals/    GoalsManager
    ui/       primitives (Spinner, SectionHeading, EmptyState, ErrorNote)
  features/chat/useChatStream.ts   SSE stream → React state
  lib/        api (fetch wrapper + useApi hook) · format
  types/      shared API types
```

## Screens

- **Home** — greeting, Modeer briefing, "Talk to Modeer", team grid, current goals.
- **AI Team** — Modeer + all nine specialists; pick one directly.
- **Agent workspace** — specialist identity, streaming chat, conversation rail,
  a subtle note when personal context informed a reply.
- **Memory** — "What my AI team knows about me"; view/add/edit/delete shared and
  specialist memories.
- **Goals** — user-defined goals and priorities.
