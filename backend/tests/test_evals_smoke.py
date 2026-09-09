"""Structural check that every agent's eval fixtures load and run.

Qualitative pass rates require a real provider; here we only assert the harness
executes end to end against the mock and produces substantive output for the
required case categories.
"""
from __future__ import annotations

import pytest

from app.agents.evals import RUBRIC_DIMENSIONS, load_cases, run_agent
from app.agents.registry import all_agents
from app.llm.mock_provider import MockLLMProvider

REQUIRED_CATEGORIES = {
    "in_domain",
    "ambiguous",
    "out_of_domain",
    "personalization",
    "bad_assumption",
    "safety",
    "quality",
}

AGENT_IDS = [a.id for a in all_agents()]


@pytest.mark.parametrize("slug", AGENT_IDS)
def test_agent_has_full_category_coverage(slug):
    cases = load_cases(slug)
    assert cases, f"{slug} has no eval cases"
    categories = {c["category"] for c in cases}
    missing = REQUIRED_CATEGORIES - categories
    assert not missing, f"{slug} missing eval categories: {missing}"
    for case in cases:
        assert case["expect"].get("rubric"), case["id"]
        assert set(case["expect"]["rubric"]) <= set(RUBRIC_DIMENSIONS), case["id"]


@pytest.mark.parametrize("slug", AGENT_IDS)
async def test_eval_harness_runs(slug):
    report = await run_agent(slug, MockLLMProvider())
    assert report.total == len(load_cases(slug))
    # every case produced a non-trivial response
    for result in report.results:
        assert len(result.output_preview) > 20, result.id
