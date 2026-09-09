"""LLM-assisted memory extraction.

Used when a real provider is configured (see ``settings.use_llm_extraction``).
The model proposes durable facts; the *same* conservative gates as the rule-based
path then decide what is actually stored (sensitive data dropped unless the user
opted in, low-confidence dropped, agent-scoped facts kept only in-domain).

One short JSON call per user message. Any failure falls back to the rule-based
extractor so a bad response never breaks a turn.
"""
from __future__ import annotations

import json

from app.core.config import settings
from app.llm.base import LLMMessage, LLMProvider
from app.memory.extraction import Candidate, extract_candidates

_SYSTEM = """You extract durable personal facts from a user's message so a
personal-assistant team can remember them long-term.

Return ONLY a JSON array (no prose, no markdown fences). Each element:
{"scope": "shared" | "agent",
 "agent_id": "<specialist slug, or null when scope is shared>",
 "category": "one of: education, career, goals, context, preferences, health,
              finance, routine, targets, weak_topics, general",
 "key": "snake_case_stable_key",
 "value": "concise factual value",
 "confidence": 0.0-1.0,
 "sensitive": true|false}

What counts as DURABLE (capture it):
- Identity & situation: studies, job, location, languages, age.
- Goals, plans and deadlines — including future-dated ones. "ML internship next
  summer", "trip to Japan in April", "exam on the 20th" are goals, not transient.
- Stable preferences, routines and hobbies: "trains 4x/week", "vegetarian",
  "learns best from examples", "budget around $1000".
- Constraints: "can't relocate", "no early flights", "works night shifts".

What is TRANSIENT (ignore it): mood or energy right now ("tired today"), what
they're doing this minute, pleasantries, and one-off questions with no lasting
fact in them.

Scope:
- "shared" = useful to several specialists (identity, goals, big preferences).
- "agent" + agent_id = domain-specific detail only that specialist needs. Slugs:
  study, career, travel, shopping, finance, fitness, writing, research, email.
  e.g. powerlifting routine -> {"scope":"agent","agent_id":"fitness",...}

Other rules:
- Split a compound sentence into separate facts. Keep values short and factual.
- sensitive=true for health conditions, medications, income/balances, government
  IDs, credentials, religion, immigration status, sexuality. Still report them.
- If the message contains no durable fact, return [].

Example
message: "I'm a final-year law student in Nairobi. I want a training contract at
a commercial firm next year, and I run 5k three mornings a week."
output:
[{"scope":"shared","agent_id":null,"category":"education","key":"field_of_study","value":"law","confidence":0.95,"sensitive":false},
 {"scope":"shared","agent_id":null,"category":"education","key":"study_year","value":"final year","confidence":0.9,"sensitive":false},
 {"scope":"shared","agent_id":null,"category":"context","key":"location","value":"Nairobi","confidence":0.95,"sensitive":false},
 {"scope":"shared","agent_id":null,"category":"goals","key":"training_contract","value":"training contract at a commercial law firm, next year","confidence":0.9,"sensitive":false},
 {"scope":"agent","agent_id":"fitness","category":"routine","key":"running","value":"5k, three mornings a week","confidence":0.85,"sensitive":false}]"""

_VALID_SCOPES = {"shared", "agent"}
_AGENT_SLUGS = {
    "study", "career", "travel", "shopping", "finance",
    "fitness", "writing", "research", "email", "modeer",
}


async def llm_extract_candidates(
    text: str,
    *,
    agent_id: str,
    provider: LLMProvider,
    model: str,
) -> list[Candidate]:
    text = (text or "").strip()
    if len(text) < 6:
        return []

    try:
        result = await provider.complete(
            system=_SYSTEM,
            messages=[LLMMessage(role="user", content=text)],
            model=model,
            temperature=0.0,
            max_tokens=550,
        )
        raw = _parse_json_array(result.text)
    except Exception:  # noqa: BLE001 - never let extraction break a turn
        return extract_candidates(text, agent_id=agent_id)

    out: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        cand = _to_candidate(item, agent_id=agent_id)
        if cand is None:
            continue
        dedupe = (cand.key, cand.value.lower())
        if dedupe in seen:
            continue
        seen.add(dedupe)
        out.append(cand)
    return out


def _parse_json_array(text: str) -> list[dict]:
    text = text.strip().strip("`")
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        # No array at all — the model didn't produce JSON. Signal a fallback.
        raise ValueError("no JSON array in response")
    data = json.loads(text[start : end + 1])
    return [d for d in data if isinstance(d, dict)]


def _to_candidate(item: dict, *, agent_id: str) -> Candidate | None:
    scope = str(item.get("scope", "shared")).lower()
    if scope not in _VALID_SCOPES:
        scope = "shared"
    value = str(item.get("value", "")).strip().rstrip(".")
    key = str(item.get("key", "")).strip().lower().replace(" ", "_")
    category = str(item.get("category", "general")).strip().lower() or "general"
    if len(value) < 2 or not key:
        return None

    target_agent: str | None = None
    if scope == "agent":
        target_agent = str(item.get("agent_id") or "").strip().lower() or None
        if target_agent not in _AGENT_SLUGS:
            # Unusable agent scope -> treat as shared.
            scope, target_agent = "shared", None
        elif target_agent == "modeer":
            scope, target_agent = "shared", None
        elif agent_id not in (target_agent, "modeer"):
            # Only capture an agent-scoped fact inside that agent's chat or Modeer.
            return None

    try:
        confidence = round(float(item.get("confidence", 0.7)), 2)
    except (TypeError, ValueError):
        confidence = 0.7
    confidence = max(0.0, min(1.0, confidence))
    sensitive = bool(item.get("sensitive", False))

    if sensitive and not settings.memory_store_sensitive:
        return Candidate(scope, target_agent, category, key, value, confidence,
                         True, False, "sensitive; not stored automatically")
    if confidence < settings.memory_min_confidence:
        return Candidate(scope, target_agent, category, key, value, confidence,
                         sensitive, False, "confidence below threshold")
    return Candidate(scope, target_agent, category, key, value, confidence,
                     sensitive, True, "durable personal fact")
