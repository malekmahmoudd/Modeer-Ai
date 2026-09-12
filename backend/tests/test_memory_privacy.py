"""Automatic memory must fail closed.

Every case here is a way model output used to reach storage when it should not
have: a missing or wrong sensitivity flag, a malformed field repaired by a
guess, a private note widened to the whole team. Alongside them sit the
ordinary facts that must still be remembered — a filter that drops everything
is not privacy, it is a broken product.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.llm.base import LLMResult
from app.memory.llm_extraction import llm_extract_candidates
from app.memory.sensitivity import looks_sensitive


class _Stub:
    name = "stub"

    def __init__(self, payload):
        self._payload = payload if isinstance(payload, str) else json.dumps(payload)

    async def complete(self, **_kwargs) -> LLMResult:
        return LLMResult(text=self._payload, model="stub", usage={})


async def _extract(*rows, agent_id: str = "modeer", raw: str | None = None):
    return await llm_extract_candidates(
        "a message the user wrote about themselves",
        agent_id=agent_id,
        provider=_Stub(raw if raw is not None else list(rows)),
        model="stub",
    )


def _fact(**overrides) -> dict:
    base = {
        "scope": "shared",
        "agent_id": None,
        "category": "education",
        "key": "field_of_study",
        "value": "mechanical engineering",
        "confidence": 0.9,
        "sensitive": False,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _consent_off(monkeypatch):
    """The shipped default: sensitive data is never stored automatically."""
    monkeypatch.setattr(settings, "memory_store_sensitive", False)


# --- legitimate facts still get through ---------------------------------------


async def test_an_ordinary_shared_fact_is_stored():
    (candidate,) = await _extract(_fact())
    assert candidate.stored and candidate.scope == "shared"


async def test_a_specialist_fact_is_stored_privately_in_its_own_chat():
    (candidate,) = await _extract(
        _fact(
            scope="agent",
            agent_id="fitness",
            category="routine",
            key="lifting",
            value="4x per week",
        ),
        agent_id="fitness",
    )
    assert candidate.stored and candidate.scope == "agent" and candidate.agent_id == "fitness"


async def test_modeers_private_notes_stay_in_modeers_namespace():
    """Modeer-scoped notes used to be promoted to shared; now they stay private."""
    (candidate,) = await _extract(
        _fact(scope="agent", agent_id="modeer", category="preferences", key="tone", value="blunt"),
    )
    assert candidate.scope == "agent" and candidate.agent_id == "modeer"


async def test_a_spending_budget_is_not_mistaken_for_income():
    (candidate,) = await _extract(
        _fact(category="preferences", key="budget", value="under 700 for a phone"),
    )
    assert candidate.stored and not candidate.sensitive


# --- sensitivity does not rest on the model's flag ----------------------------


async def test_sensitive_fact_flagged_false_by_the_model_is_withheld():
    (candidate,) = await _extract(
        _fact(category="context", key="condition", value="diagnosed with depression"),
    )
    assert candidate.sensitive and not candidate.stored


async def test_missing_sensitivity_flag_is_treated_as_sensitive():
    row = _fact()
    del row["sensitive"]
    (candidate,) = await _extract(row)
    assert candidate.sensitive and not candidate.stored


@pytest.mark.parametrize("flag", ["false", 0, None, "no", []])
async def test_a_non_boolean_flag_is_treated_as_sensitive(flag):
    (candidate,) = await _extract(_fact(sensitive=flag))
    assert candidate.sensitive and not candidate.stored


async def test_the_health_category_is_sensitive_whatever_the_flag_says():
    (candidate,) = await _extract(
        _fact(category="health", key="allergy", value="peanuts"),
    )
    assert candidate.sensitive and not candidate.stored


async def test_consent_opt_in_stores_sensitive_facts():
    settings.memory_store_sensitive = True
    (candidate,) = await _extract(_fact(category="health", key="allergy", value="peanuts"))
    assert candidate.stored and candidate.sensitive


# --- malformed output is rejected, never repaired ------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"scope": "everyone"},
        {"scope": None},
        {"scope": 1},
        {"category": "astrology"},
        {"key": "Not A Key!"},
        {"key": 7},
        {"value": {"nested": "dict"}},
        {"value": ["a", "list"]},
        {"value": "x"},
        {"value": "y" * 301},
        {"confidence": "high"},
        {"confidence": None},
        {"confidence": True},
        {"confidence": 1.7},
        {"confidence": -0.1},
    ],
)
async def test_malformed_fields_are_rejected(overrides):
    assert await _extract(_fact(**overrides)) == []


@pytest.mark.parametrize("field", ["scope", "key", "value", "category", "confidence"])
async def test_a_missing_required_field_is_rejected(field):
    row = _fact()
    del row[field]
    assert await _extract(row) == []


async def test_non_json_output_falls_back_to_rules_not_to_guessing():
    out = await _extract(raw="I could not find any facts, sorry.")
    assert all(c.scope != "agent" or c.agent_id for c in out)


# --- private scope is never widened --------------------------------------------


@pytest.mark.parametrize("agent", ["astrology", "Fitnes", "", "   ", None, 42])
async def test_an_unusable_agent_scope_is_rejected_not_shared(agent):
    out = await _extract(_fact(scope="agent", agent_id=agent))
    assert out == [], "a private note was widened into shared memory"


async def test_shared_scope_naming_a_specialist_is_rejected():
    """Contradictory: the private reading must win, so it is not stored as shared."""
    assert await _extract(_fact(scope="shared", agent_id="finance")) == []


async def test_a_specialists_private_fact_is_not_captured_in_another_chat():
    assert (
        await _extract(
            _fact(
                scope="agent",
                agent_id="fitness",
                category="routine",
                key="lifting",
                value="4x per week",
            ),
            agent_id="study",
        )
        == []
    )


# --- the backstop itself -------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "takes antidepressants",
        "my salary is 60k",
        "passport number 123",
        "is a practising Muslim",
        "has a criminal record",
        "recovering from a knee injury",
    ],
)
def test_backstop_catches_common_sensitive_phrasing(text):
    assert looks_sensitive(text)


@pytest.mark.parametrize(
    "text",
    [
        "studies mechanical engineering",
        "trains four times a week",
        "budget around 1000 for a laptop",
        "wants to visit temples in Kyoto",
        "prefers slow travel",
    ],
)
def test_backstop_leaves_ordinary_facts_alone(text):
    assert not looks_sensitive(text)
