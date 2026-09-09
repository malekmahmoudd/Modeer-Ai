"""Provider factory. One provider at a time, chosen by settings."""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockLLMProvider


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower().strip()
    if provider in ("", "mock", "none"):
        return MockLLMProvider()
    if provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings.llm_api_key, settings.llm_base_url)
    raise ValueError(
        f"Unsupported LLM_PROVIDER={provider!r}. Use 'mock' or 'anthropic'."
    )


def resolve_model(override: str | None) -> str:
    return override or settings.llm_model
