"""Deterministic mock provider.

Runs with no API key so the whole product is usable and testable offline. It is
context-aware on purpose: it echoes the personal-context and agent-memory blocks
that the runtime injected, which is exactly what the end-to-end milestone needs
to demonstrate ("the Career Agent already knows the fact").
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

from app.llm.base import LLMMessage, LLMProvider

_BLOCK = re.compile(
    r"<<(?P<tag>[A-Z_]+)>>\s*(?P<body>.*?)\s*<</(?P=tag)>>", re.DOTALL
)
_ROLE = re.compile(r"^# ACTIVE AGENT:\s*(?P<name>[^\n—-]+)", re.MULTILINE)


class MockLLMProvider(LLMProvider):
    name = "mock"

    async def stream_chat(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        text = self._compose(system, messages)
        for token in _tokenize(text):
            await asyncio.sleep(0)  # cooperative; keeps streaming semantics
            yield token

    # -- internals -------------------------------------------------------
    @staticmethod
    def _compose(system: str, messages: list[LLMMessage]) -> str:
        blocks = {m.group("tag"): m.group("body").strip() for m in _BLOCK.finditer(system)}
        name_match = _ROLE.search(system)
        agent_name = name_match.group("name").strip() if name_match else "Your assistant"

        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        personal = _bullets(blocks.get("PERSONAL_CONTEXT", ""))
        agent_mem = _bullets(blocks.get("AGENT_MEMORY", ""))

        lines: list[str] = []
        lines.append(f"[{agent_name} — offline preview response]")
        lines.append("")
        if last_user:
            snippet = last_user.strip().replace("\n", " ")
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."
            lines.append(f"You asked: “{snippet}”")
            lines.append("")
        if personal:
            lines.append("Using what the team already knows about you:")
            lines.extend(f"  • {p}" for p in personal)
            lines.append("")
        if agent_mem:
            lines.append(f"From my own notes ({agent_name}):")
            lines.extend(f"  • {p}" for p in agent_mem)
            lines.append("")
        lines.append(
            "This is a placeholder generated without a language model. Set "
            "LLM_PROVIDER=anthropic and LLM_API_KEY in backend/.env to get real "
            "specialist responses. The personal context above proves the shared "
            "memory pipeline is working."
        )
        return "\n".join(lines)


def _bullets(body: str) -> list[str]:
    out: list[str] = []
    for raw in body.splitlines():
        line = raw.strip().lstrip("-•*").strip()
        if line and not line.lower().startswith("(none"):
            out.append(line)
    return out


def _tokenize(text: str) -> list[str]:
    # Emit word-plus-trailing-space chunks to mimic token streaming.
    parts = re.split(r"(\s+)", text)
    chunks: list[str] = []
    buf = ""
    for p in parts:
        buf += p
        if not p.isspace():
            continue
        chunks.append(buf)
        buf = ""
    if buf:
        chunks.append(buf)
    return chunks or [text]
