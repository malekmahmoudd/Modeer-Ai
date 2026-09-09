# Agent design system

Specialists must **not** differ only by a flavour line like "You are an expert
Study Agent." Each has an explicit **domain reasoning framework** — an ordered
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
## Non-negotiable rules                                      ← global guardrails
## About the user
## Personal context (shared)   <<PERSONAL_CONTEXT>> … <</PERSONAL_CONTEXT>>
## Your private notes          <<AGENT_MEMORY>> … <</AGENT_MEMORY>>
## Current goals and priorities
```

The framework is **internal scaffolding**: the guardrails explicitly forbid
reproducing it or narrating hidden chain-of-thought. Output is conclusions,
options, and rationale — never a private reasoning trace.

## The frameworks (summary)

| Agent | Reasoning framework (internal) |
|---|---|
| **Modeer** | clarify intent → recall what's known → pick mode (onboard/capture/plan/advise/route) → route if a specialist fits → answer directly → note durable facts → concrete next step |
| **Study** | objective → assess current knowledge → find the gap/misconception → choose strategy → explain at right depth → concrete example + check → next practice step → record preferences |
| **Career** | objective/decision → career stage → constraints → real options (incl. unstated) → use personal background → challenge weak assumptions → concrete next actions → record targets/CV state |
| **Research** | pin the question → scope + success criteria → known/contested/unknown → structure sub-questions + evidence types → reason from evidence → weigh quality → calibrated synthesis with confidence |
| **Writing** | purpose/audience/effect → core message → diagnose top-down (structure→para→line) → work in the user's voice → cut and strengthen → teach the 2–3 changes that matter |
| **Travel** | frame trip (purpose/dates/party/budget) → travel style → destination/season fit → shape before detail → sequence logistics → budget split → time-sensitive calls → record preferences |
| **Shopping** | real need + use → budget/constraints → 3–5 ranked criteria → viable categories → compare incl. total cost of ownership → check over/under-buying → pick + runner-up with the trade-off |
| **Finance** | decision + horizon → picture the user shares → real constraint (cash flow/risk/time) → options with mechanics + rules of thumb → downside stress-test → framework + next steps → when to see a professional |
| **Fitness** | goal → training age + limitations → real constraints (days/time/equipment) → fit program structure → progression + deload → design for adherence → review points → record schedule/equipment/injuries |
| **Email** | goal (know/feel/do) → relationship + power dynamic → constraints → structure (BLUF) → draft in voice at register → pressure-test tone → subject line + call to action |

Full text is in each `prompt.md`.

## Shared context each agent requests

`shared_context_fields` on the config filters which shared-memory categories are
injected (empty = all; Modeer sees everything). E.g. Career pulls
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
