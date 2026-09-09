"""Typed agent configuration.

An agent is data, not code: a slug, presentation metadata, an explicit domain
reasoning framework, behavioural rules, safety boundaries and model settings.
The large natural-language system instructions live next to it in ``prompt.md``.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    model: str | None = None  # overrides the global LLM_MODEL when set
    temperature: float = 0.6
    max_tokens: int = 1024


class AgentConfig(BaseModel):
    # --- identity ---
    id: str
    name: str
    role: str
    description: str
    icon: str = "✨"
    accent: str = "#6366f1"
    is_assistant: bool = False  # True only for Modeer
    sort_order: int = 100

    # --- presentation (drives the UI; no logic here) ---
    tagline: str = ""  # ultra-short, e.g. "Jobs, CVs, interviews"
    composer_placeholder: str = ""  # e.g. "Ask about your career…"
    empty_prompt: str = ""  # the question shown on a fresh chat
    starters: list[str] = Field(default_factory=list)  # 3-4 example openers

    # --- capability ---
    expertise: list[str] = Field(default_factory=list)
    # Shared-context categories this specialist actively wants injected.
    shared_context_fields: list[str] = Field(default_factory=list)
    memory_namespace: str = ""

    # --- behaviour ---
    # The explicit domain reasoning framework. Internal scaffolding for the
    # model's own process; never surfaced verbatim to the user.
    reasoning_framework: list[str] = Field(default_factory=list)
    response_behavior: list[str] = Field(default_factory=list)
    safety_boundaries: list[str] = Field(default_factory=list)

    # --- model ---
    model: ModelConfig = Field(default_factory=ModelConfig)
    prompt_version: int = 1

    # Filled by the registry from prompt.md.
    system_prompt: str = ""

    @property
    def namespace(self) -> str:
        return self.memory_namespace or self.id
