"""Discovers agent configurations from ``app/agents/<slug>/``.

Each agent folder contains:
  * ``config.py``  -> module-level ``CONFIG: AgentConfig``
  * ``prompt.md``  -> natural-language system instructions
  * ``evals.json`` -> evaluation fixtures (see app/agents/evals.py)
"""
from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache
from pathlib import Path

from app.agents.schema import AgentConfig

_PKG = "app.agents"
_DIR = Path(__file__).parent


def _load_prompt(slug: str) -> str:
    path = _DIR / slug / "prompt.md"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


@lru_cache(maxsize=1)
def _load_all() -> dict[str, AgentConfig]:
    agents: dict[str, AgentConfig] = {}
    for mod in pkgutil.iter_modules([str(_DIR)]):
        if not mod.ispkg:
            continue
        try:
            config_mod = importlib.import_module(f"{_PKG}.{mod.name}.config")
        except ModuleNotFoundError:
            continue
        cfg: AgentConfig | None = getattr(config_mod, "CONFIG", None)
        if cfg is None:
            continue
        cfg = cfg.model_copy(update={"system_prompt": _load_prompt(mod.name)})
        agents[cfg.id] = cfg
    return dict(sorted(agents.items(), key=lambda kv: kv[1].sort_order))


def all_agents() -> list[AgentConfig]:
    return list(_load_all().values())


def specialists() -> list[AgentConfig]:
    return [a for a in all_agents() if not a.is_assistant]


def get_agent(slug: str) -> AgentConfig | None:
    return _load_all().get(slug)


def require_agent(slug: str) -> AgentConfig:
    agent = get_agent(slug)
    if agent is None:
        raise KeyError(f"Unknown agent: {slug!r}")
    return agent


def reload() -> None:
    """Test/hot-reload helper."""
    _load_all.cache_clear()
