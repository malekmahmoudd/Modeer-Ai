# Agent design system

Specialists must **not** differ only by a flavour line like "You are an expert
Nova." Each has an explicit **domain reasoning framework** — an ordered
method it runs internally — plus behavioural rules, safety boundaries, and model
settings.

## Anatomy of an agent

`backend/app/agents/<slug>/`

| File | Purpose |
|---|---|
| `config.py` | `CONFIG: AgentConfig` — id, name, role, description, icon, accent, `expertise`, `shared_context_fields`, `memory_namespace`, `reasoning_framework`, `response_behavior`, `safety_boundaries`, `model`, `prompt_version`, plus presentation: `tagline`, `composer_placeholder`, `empty_prompt`, `starters` (served by the API so the UI stays config-driven) |
| `prompt.md` | The natural-language system instructions (versioned, reviewable, not buried in code) |
| `evals.json` | Evaluation fixtures (see below) |

At runtime `context.py` composes the system message:

```
# ACTIVE AGENT: <name> — <role>
<prompt.md>
## Operating framework (internal — never output verbatim)   ← reasoning_framework
## Response behaviour                                        ← response_behavior
## Safety boundaries                                         ← safety_boundaries
## About the user
## Personal context (shared)   <<PERSONAL_CONTEXT>> … <</PERSONAL_CONTEXT>>
## Your private notes          <<AGENT_MEMORY>> … <</AGENT_MEMORY>>
## Notes teammates passed you  <<HANDOFFS>> … <</HANDOFFS>>     (when any)
## Current goals and priorities
## Today                                                     ← date/time in the user's zone
## Recent activity across the team (titles only)             ← Leo only
## Rules (internal — never quote them)                       ← shared rules, 8 numbered
```

The shared rules were ~7k characters (half of every prompt) until 2026-09-25.
They are now one numbered block of ~2.5k characters with the same content.
Rule 7 (dates) has two forms. In the live app the agent is given today's date
and resolves relative dates ("next Thursday (2 October)"). Without a date, as
in the evals, it is told it does not know today's date and must keep dates as
given. The rubric's date checks (`app/agents/rubric.py`) assume the second
form. The dated form has no eval cases yet.

## Time

The browser sends its IANA zone as `X-Timezone` with every chat message. A
valid zone is saved on the account (`users.timezone`, migration 0005; also
settable with `PATCH /api/users/me {"timezone": …}`). Agents get the current
date and time in that zone. Until one is known they get UTC and are told the
local date may differ by one day. The daily briefing uses the user's own date,
and shows "Due Thu 1 Oct — in 6 days" for goals with a target date. See
`app/core/clock.py`.

## Working as a team

Agents still never read each other's transcripts. What crosses between them is
narrow and visible (`app/agents/team.py`):

- **Leo sees recent activity**: the titles of up to 8 recent conversations with
  specialists and how long ago they were, plus notes waiting for teammates.
  Never their contents.
- **Leo changes goals when asked**: an explicit request ("add a marathon to my
  goals", "mark Spanish done", "make the CV my top priority") comes back from the
  turn analysis as a goal change. It is validated (known op, real goal number,
  priority 1–5), applied to Goals, and reported in the `memory` event. Only Leo's
  turns can change goals.
- **Handoffs**: when the person asks any agent to pass something to a named
  teammate ("tell Harvey about the interview"), the analysis returns a short
  brief. It is stored as that teammate's private note (category `handoff`, key
  `from_<sender>`; a newer note from the same sender replaces the older one and
  keeps it in history). The teammate sees it under "Notes teammates passed
  you", and the person can read or delete it on the Memory page. A handoff goes
  only to a teammate the person actually named in the message, never to the
  sender itself, and a brief that looks sensitive is not passed on
  automatically.
- These requests still work with automatic memory switched off, because the
  person asked for them explicitly. Facts are not learned then.

The framework is **internal scaffolding**: the guardrails explicitly forbid
reproducing it or narrating hidden chain-of-thought. Output is conclusions,
options, and rationale — never a private reasoning trace.

## The frameworks (summary)

| Agent | Reasoning framework (internal) |
|---|---|
| **Leo** | clarify intent → recall what's known → pick mode (onboard/capture/plan/advise/route) → route if a specialist fits → answer directly → note durable facts → concrete next step |
| **Nova (Study)** | objective → assess current knowledge → find the gap/misconception → choose strategy → explain at right depth → concrete example + check → next practice step → record preferences |
| **Harvey (Career)** | objective/decision → career stage → constraints → real options (incl. unstated) → use personal background → challenge weak assumptions → concrete next actions → record targets/CV state |
| **Clara (Research)** | pin the question → scope + success criteria → known/contested/unknown → structure sub-questions + evidence types → reason from evidence → weigh quality → calibrated synthesis with confidence |
| **Alex (Writing)** | purpose/audience/effect → core message → diagnose top-down (structure→para→line) → work in the user's voice → cut and strengthen → teach the 2–3 changes that matter |
| **Tessa (Travel)** | frame trip (purpose/dates/party/budget) → travel style → destination/season fit → shape before detail → sequence logistics → budget split → time-sensitive calls → record preferences |
| **Nate (Shopping)** | real need + use → budget/constraints → 3–5 ranked criteria → viable categories → compare incl. total cost of ownership → check over/under-buying → pick + runner-up with the trade-off |
| **Emma (Finance)** | decision + horizon → picture the user shares → real constraint (cash flow/risk/time) → options with mechanics + rules of thumb → downside stress-test → framework + next steps → when to see a professional |
| **Maddie (Fitness)** | goal → training age + limitations → real constraints (days/time/equipment) → fit program structure → progression + deload → design for adherence → review points → record schedule/equipment/injuries |
| **Nora (Email)** | goal (know/feel/do) → relationship + power dynamic → constraints → structure (BLUF) → draft in voice at register → pressure-test tone → subject line + call to action |

Full text is in each `prompt.md`.

## Shared context each agent requests

`shared_context_fields` on the config filters which shared-memory categories are
injected (empty = all; Leo sees everything). E.g. Career pulls
`career, education, goals, context`; Email pulls `career, context`. Pinned
memories are always included.

## Evaluations

`app/agents/evals.py` + `<slug>/evals.json`. Every agent has cases in all seven
categories:

`in_domain · ambiguous · out_of_domain · personalization · bad_assumption ·
safety · quality`

Each case declares expectations (`mentions_any`, `mentions_all`, `not_mentions`,
`redirects_to`, `asks_clarifying`) and a `rubric` (subset of: relevance,
specialization, usefulness, clarity, personalization, scope_discipline, safety).

```bash
python -m app.agents.evals                 # all agents, mock provider (structural)
python -m app.agents.evals study --json
LLM_PROVIDER=anthropic LLM_API_KEY=… python -m app.agents.evals   # qualitative
```

Scoring is deterministic heuristics so it runs in CI; pass rates are only
meaningful against a real provider. `tests/test_evals_smoke.py` asserts coverage
and that the harness runs.

## Adding an agent

1. `mkdir backend/app/agents/<slug>` with `__init__.py`, `config.py`,
   `prompt.md`, `evals.json`.
2. Restart. The registry discovers it; startup syncs the `agents` table; the
   frontend `/team` grid and `/agents/<slug>` workspace pick it up automatically.
