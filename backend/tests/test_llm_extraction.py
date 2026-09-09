"""LLM-extraction path: deterministic tests with a stubbed provider.

No network. Verifies JSON parsing, the safety/confidence gates (shared with the
rule-based path), agent-scope routing, and graceful fallback on bad output.
"""
from __future__ import annotations

import json

from app.llm.base import LLMResult
from app.memory.llm_extraction import llm_extract_candidates


class StubProvider:
    name = "stub"

    def __init__(self, payload: str):
        self._payload = payload

    async def complete(self, **_kwargs) -> LLMResult:
        return LLMResult(text=self._payload, model="stub", usage={})


def _rows(*objs) -> str:
    return json.dumps(list(objs))


async def _run(payload: str, *, agent_id: str = "modeer"):
    return await llm_extract_candidates(
        "some user message about themselves",
        agent_id=agent_id,
        provider=StubProvider(payload),
        model="stub",
    )


async def test_parses_and_stores_durable_shared_fact():
    out = await _run(
        _rows(
            {"scope": "shared", "agent_id": None, "category": "goals",
             "key": "ml_internship", "value": "ML internship next summer",
             "confidence": 0.95, "sensitive": False}
        )
    )
    assert len(out) == 1
    c = out[0]
    assert c.stored and c.scope == "shared" and c.category == "goals"
    assert "ML internship" in c.value


async def test_sensitive_is_flagged_and_not_stored():
    out = await _run(
        _rows(
            {"scope": "shared", "agent_id": None, "category": "finance",
             "key": "salary", "value": "45000", "confidence": 0.99,
             "sensitive": True}
        )
    )
    assert out and out[0].sensitive is True and out[0].stored is False


async def test_low_confidence_is_dropped():
    out = await _run(
        _rows(
            {"scope": "shared", "agent_id": None, "category": "context",
             "key": "maybe_city", "value": "Berlin?", "confidence": 0.2,
             "sensitive": False}
        )
    )
    assert out and out[0].stored is False


async def test_agent_scope_routes_and_is_gated_by_current_agent():
    obj = {"scope": "agent", "agent_id": "fitness", "category": "routine",
           "key": "lifting", "value": "4x/week", "confidence": 0.9,
           "sensitive": False}
    # From Modeer: allowed, routed to the fitness namespace.
    from_modeer = await _run(_rows(obj), agent_id="modeer")
    assert from_modeer and from_modeer[0].agent_id == "fitness" and from_modeer[0].stored
    # Inside the Study chat: a fitness-scoped fact is not captured.
    from_study = await _run(_rows(obj), agent_id="study")
    assert from_study == []


async def test_unknown_agent_scope_falls_back_to_shared():
    out = await _run(
        _rows(
            {"scope": "agent", "agent_id": "astrology", "category": "general",
             "key": "sign", "value": "libra", "confidence": 0.9, "sensitive": False}
        )
    )
    assert out and out[0].scope == "shared" and out[0].agent_id is None


async def test_json_wrapped_in_prose_and_fences_is_recovered():
    payload = (
        "Sure, here you go:\n```json\n"
        + _rows({"scope": "shared", "agent_id": None, "category": "education",
                 "key": "major", "value": "law", "confidence": 0.9,
                 "sensitive": False})
        + "\n```\nHope that helps!"
    )
    out = await _run(payload)
    assert len(out) == 1 and out[0].value == "law"


async def test_garbage_output_falls_back_to_rule_extractor():
    # Not JSON at all -> falls back to rules, which catch the studying pattern.
    out = await llm_extract_candidates(
        "I am studying naval architecture at Chalmers.",
        agent_id="modeer",
        provider=StubProvider("the model refused to answer"),
        model="stub",
    )
    assert any("naval architecture" in c.value for c in out)


async def test_empty_array_yields_nothing():
    assert await _run("[]") == []
