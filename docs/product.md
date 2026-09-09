# Product

## What it is

A personal AI assistant, **Modeer**, plus a user-chosen team of nine specialist
AI agents that **share personal context**. The user opens the app, sees the team,
picks who to talk to, and chats with that specialist directly. Going through
Modeer is never required.

## The team

| Agent | Role |
|---|---|
| **Modeer** | Personal assistant & context keeper (onboarding, shared context, goals, daily briefing, routing) |
| Study | Learning coach & explainer |
| Career | Career strategist & coach |
| Research | Research analyst & sense-maker |
| Writing | Writing partner & editor |
| Travel | Trip planner & advisor |
| Shopping | Purchase advisor |
| Finance | Personal finance guide (educational) |
| Fitness | Training & habit coach (non-medical) |
| Email | Email drafting & correspondence coach |

Implementation depth is concentrated first on **Modeer, Study, Career, Research,
Writing**; all nine run on the same runtime with no duplicated backend.

## What Modeer is and isn't

Modeer **does**: onboard the user, learn durable personal facts, maintain shared
context, help define goals, give general help, produce a daily briefing from
stored data, and suggest a specialist when one fits.

Modeer **does not**: silently route every request, gate access to specialists,
take autonomous actions, or perform a fictional-character persona. The JARVIS
inspiration is about awareness and usefulness, not impersonation.

## Explicitly out of scope for the MVP

Tools, browser access, Gmail/calendar access, payments, booking, purchasing,
autonomous actions, MCP, a marketplace, a developer SDK, microservices,
Kubernetes, agent frameworks (LangChain / LangGraph / CrewAI / AutoGen), and
vector databases.

## Priorities

1. Excellent UI/UX — a premium personal AI command center, not "ChatGPT with nine
   custom GPTs in a sidebar".
2. Excellent specialist-agent performance — each specialist has an explicit
   domain reasoning framework, not just a flavour prompt.
3. Shared personal context that makes the whole team feel like it knows the user.

## First milestone

Modeer learns a durable fact → it enters shared context → Career and Study each
use it in their own domain, with independent histories → the user can view and
edit/delete it in "What my AI team knows about me". Covered end to end by
`backend/tests/test_milestone_flow.py`.

## Ask My Team

Secondary. A minimal, explicit, user-controlled endpoint (`POST /api/team/ask`)
where the user selects specialists, each answers through the shared runtime, and
Modeer synthesises. Not automatic, not autonomous. Built after the core 1:1 chat.
