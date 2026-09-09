from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.registry import all_agents, get_agent

router = APIRouter(prefix="/agents", tags=["agents"])


def _public(agent) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "description": agent.description,
        "icon": agent.icon,
        "accent": agent.accent,
        "is_assistant": agent.is_assistant,
        "sort_order": agent.sort_order,
        "expertise": agent.expertise,
        "tagline": agent.tagline or agent.role,
        "composer_placeholder": agent.composer_placeholder or f"Message {agent.name}…",
        "empty_prompt": agent.empty_prompt or f"How can {agent.name} help?",
        "starters": agent.starters,
    }


def _detail(agent) -> dict:
    return {
        **_public(agent),
        "reasoning_framework": agent.reasoning_framework,
        "response_behavior": agent.response_behavior,
        "safety_boundaries": agent.safety_boundaries,
        "shared_context_fields": agent.shared_context_fields,
        "memory_namespace": agent.namespace,
        "prompt_version": agent.prompt_version,
        "model": agent.model.model_dump(),
    }


@router.get("")
def list_agents() -> list[dict]:
    return [_public(a) for a in all_agents()]


@router.get("/{agent_id}")
def get_agent_detail(agent_id: str) -> dict:
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Unknown agent")
    return _detail(agent)
