# Memory

Two layers, both fully transparent and user-editable in the app under
**"What my AI team knows about me"** (`/memory`).

## Layers

### Shared personal context (`shared_memories`)

Facts useful across multiple specialists: education, career goals, major
priorities, stable preferences, long-term goals, general constraints, location.
Visible to every agent (filtered per agent by `shared_context_fields`).

### Agent-specific memory (`agent_memories`)

Private to one specialist; `namespace = agent slug`. Examples:

| Agent | Typical notes |
|---|---|
| Study | subjects, weak topics, preferred explanation style |
| Career | target roles, CV state, interview weaknesses |
| Travel | destination preferences, travel style |
| Fitness | schedule, equipment, routine, injury history |

## Item shape

`id · user_id · scope · agent_id (agent layer) · category · key · value ·
source · confidence · sensitive · created_at · updated_at`
(shared items also carry `pinned`.)

`source` is `user`, `modeer`, or a specialist slug. `(user_id, key)` is unique
for shared; `(user_id, agent_id, key)` for agent — writes upsert.

## Extraction (`app/memory/extraction.py`)

Deterministic and rule-based — memory writes must be predictable, and the MVP
avoids LLM/tool-driven autonomy. After each user message the runtime extracts
candidates and classifies each into one of four cases:

| Case | Action |
|---|---|
| **Temporary detail** ("tired today", "good morning") | not stored |
| **Durable shared info** ("I'm studying X", "I want to become Y", "I live in Z") | → shared context |
| **Useful specialist info** ("I learn best by diagrams" in Study) | → that agent's namespace |
| **Should not be stored** (health, salary, IDs, credentials, religion, …) | flagged `sensitive`, **not stored** unless `MEMORY_STORE_SENSITIVE=true` |

Other guards: confidence is reduced for hedged statements ("maybe", "I think")
and dropped below `MEMORY_MIN_CONFIDENCE` (default 0.55); agent-scoped rules only
fire inside their own agent's chat (or Modeer); captured values are clipped to
the noun phrase (trailing clauses removed).

The `end` SSE event returns every candidate with its `stored` flag and a
`reason`, so the UI can show "Saved to your context: …" and the user stays in
control.

## What a specialist receives

```
system instructions
+ its reasoning framework / behaviour / safety
+ relevant shared context   (filtered)
+ its own namespace memory
+ this conversation's history
```

Never another agent's raw transcript or private memory.

## API

| Method | Path | |
|---|---|---|
| GET | `/api/memory/shared` | list |
| POST | `/api/memory/shared` | add (upsert on key) |
| PATCH | `/api/memory/shared/{id}` | edit |
| DELETE | `/api/memory/shared/{id}` | delete |
| GET | `/api/memory/agent/{agent_id}` | list one namespace |
| POST | `/api/memory/agent` | add (needs `agent_id`) |
| PATCH / DELETE | `/api/memory/agent/{id}` | edit / delete |

No vector database. If semantic recall is ever proven necessary, it slots in
behind `context_for_agent` without touching agents or the runtime.
