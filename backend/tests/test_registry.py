from __future__ import annotations

from app.agents.registry import all_agents, get_agent, require_agent, specialists

EXPECTED = {
    "modeer", "study", "travel", "shopping", "career",
    "finance", "fitness", "writing", "research", "email",
}


def test_all_ten_agents_load():
    ids = {a.id for a in all_agents()}
    assert ids == EXPECTED


def test_exactly_one_assistant_and_nine_specialists():
    assert len([a for a in all_agents() if a.is_assistant]) == 1
    assert len(specialists()) == 9
    assert get_agent("modeer").is_assistant is True


def test_every_agent_has_prompt_and_framework():
    for agent in all_agents():
        assert len(agent.system_prompt) > 300, agent.id
        assert len(agent.reasoning_framework) >= 5, agent.id
        assert agent.response_behavior, agent.id
        assert agent.safety_boundaries, agent.id
        assert agent.namespace == agent.id


def test_agents_are_sorted_by_sort_order():
    orders = [a.sort_order for a in all_agents()]
    assert orders == sorted(orders)
    assert all_agents()[0].id == "modeer"


def test_require_agent_raises_for_unknown():
    try:
        require_agent("nope")
    except KeyError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected KeyError")


def test_model_config_defaults_present():
    for agent in all_agents():
        assert agent.model.max_tokens > 0
        assert 0.0 <= agent.model.temperature <= 1.0
