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
source · confidence · sensitive · history · created_at · updated_at`
(shared items also carry `pinned`.)

`source` is `user`, `modeer`, or a specialist slug. `(user_id, key)` is unique
for shared; `(user_id, agent_id, key)` for agent — writes upsert.

## Updates, duplicates, history (since 2026-09-25)

- **One fact, one row.** Keys that name the same thing are grouped in
  `app/memory/keys.py` ("city", "location", "lives_in", …). Dietary
  restrictions and allergies are deliberately *not* grouped with diet:
  "vegetarian" must never overwrite "nut allergy". A new value under
  any of them updates the row that already exists, under its existing key. The
  analyzer is also given the person's existing keys and asked to reuse them.
- **The same value is not stored twice.** A candidate with the value already
  stored under its key is reported "already remembered". So is a value of 10+
  characters already stored under another key in the same category.
- **Nothing is silently replaced.** An update pushes the old value, its source
  and when it changed onto the row's `history` (last 5 kept; migration 0005).
  The candidate carries `previous_value`, and the chat notice shows "(was …)".
  Editing a value by hand on the Memory page clears its history instead: a
  correction is often made to remove something, and the old words must go.
  Deleting a fact deletes its history. Both are in the data export.
- A value the person saved or edited themselves (`source = user`) is still
  never overwritten automatically.
- **Where it came from.** Each learned fact records `source_message_id`, the
  user message it came from. `GET /api/memory/{shared|agent}/{id}/source` returns
  an excerpt of that message, the agent and when it was said, plus the history.
  `POST /api/memory/{shared|agent}/{id}/undo` puts back the value the last
  automatic update replaced. A save or edit by hand clears both.

## Pasted text

`app/memory/pasted.py` removes what the person pasted before anything is
learned: quoted `>` lines, code fences, email header blocks (two or more of
From/To/Subject/…), forwarded or "On … wrote:" markers, and a long block after
an introducing line that ends in a colon ("Here's what she sent:"). A short
closing request after a paste ("Can you help me reply? I'm the team lead") is
kept, because it is the person talking again. Removed spans become
`[pasted text omitted]`, and the analyzer is told that facts about other people
or from pasted text are not the user's. This runs for both the LLM and the rules
path.

## Extraction

Two implementations behind one seam; `settings.memory_extraction`
(`auto` | `llm` | `rules`, default `auto`) selects. `auto` = LLM when a real
provider is configured, rules otherwise. Rules always run for `mock` and in
tests, so the suite stays deterministic.

- **Rules** (`app/memory/extraction.py`) — regex patterns for common first-person
  statements. Predictable, zero-cost, brittle on natural phrasing.
- **LLM** (`app/memory/llm_extraction.py`, `analyze_turn`) — one short
  JSON-only call returns `{"facts": [...], "goal_changes": [...], "handoff": …}`.
  It runs only when the message could hold something (`worth_analyzing`: first
  person, non-English text, an answer to the agent's question, a named teammate,
  or a goal request to Leo). Plain questions are not analysed. It is given today's
  date in the user's zone and writes dates as absolute ones ("interview on Thu 1
  Oct 2026"). `MEMORY_MODEL` picks its model (empty = the agent's). **The same
  gates below** then decide what is stored. Malformed output falls back to the
  rules. It runs *after* the reply has streamed, so there is no perceived latency.
  Goal changes and handoffs are described in `agents.md` ("Working as a team").

Either way, each candidate is classified into one of four cases:

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

The `memory` SSE event returns every candidate with its `stored` flag, a
`reason` and any `previous_value`, plus `goal_changes` and `handoffs`, so the UI
can show "Saved to your context: …" and the user stays in control.

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

No vector database. Documents the user uploads are searched by a local
embedding model over plain tables (`docs/rag.md`); memory facts are not.
Passages from documents never become facts.
