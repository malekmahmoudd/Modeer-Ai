"""Check the configured LLM provider: reachability, latency, limits, models.

Replaces the one-off diagnose_*/available_models scripts written while chasing
slow replies. The finding then was that Groq itself answers in 1-3s and the
delay came from a retry loop hiding rate-limit waits, so this reports the
rate-limit headers next to the timing — that pair is what makes a slow run
explicable.

    python -m tools.provider_doctor              # ping + limits
    python -m tools.provider_doctor --models     # list available models
    python -m tools.provider_doctor --stream     # time the first streamed token
    python -m tools.provider_doctor --agent study  # full agent prompt, real size
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

import httpx

from app.core.config import settings


def _base_url() -> str:
    return (settings.llm_base_url or "https://api.groq.com/openai/v1").rstrip("/")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.llm_api_key}"}


def _limits(response: httpx.Response) -> dict[str, str]:
    return {
        key: value
        for key, value in response.headers.items()
        if "ratelimit" in key.lower() or key.lower() == "retry-after"
    }


async def list_models() -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{_base_url()}/models", headers=_headers())
    ids = sorted(m["id"] for m in response.json().get("data", []))
    print(f"{len(ids)} models available:")
    for model_id in ids:
        marker = " <- configured" if model_id == settings.llm_model else ""
        print(f"  {model_id}{marker}")


async def ping(agent_slug: str | None) -> None:
    """One non-streaming request, reporting latency beside the rate-limit budget."""
    if agent_slug:
        from app.agents.context import build_context
        from app.agents.evals import _fake_mem, _fake_user, load_cases
        from app.agents.registry import require_agent

        agent = require_agent(agent_slug)
        case = next(c for c in load_cases(agent_slug) if c["category"] == "personalization")
        packet = build_context(
            agent=agent,
            user=_fake_user(),
            shared=_fake_mem(case.get("shared_context", [])),
            agent_memory=_fake_mem(case.get("agent_memory", [])),
            goals=[],
            history=[],
            user_message=case["input"],
        )
        messages = [{"role": "system", "content": packet.system}] + [
            {"role": m.role, "content": m.content} for m in packet.messages
        ]
        max_tokens = agent.model.max_tokens
    else:
        messages = [{"role": "user", "content": "Say hello in one sentence."}]
        max_tokens = 256

    payload: dict = {"model": settings.llm_model, "messages": messages}
    if settings.llm_model.startswith("openai/gpt-oss"):
        payload["max_completion_tokens"] = max_tokens
        payload["reasoning_effort"] = settings.llm_reasoning_effort
    else:
        payload["max_tokens"] = max_tokens

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{_base_url()}/chat/completions", headers=_headers(), json=payload
        )
    body = response.json()
    choice = (body.get("choices") or [{}])[0]
    print(
        json.dumps(
            {
                "model": settings.llm_model,
                "agent": agent_slug,
                "status": response.status_code,
                "seconds": round(time.monotonic() - started, 2),
                "limits": _limits(response),
                "usage": body.get("usage"),
                "finish_reason": choice.get("finish_reason"),
                "error": body.get("error"),
                "reply": (choice.get("message") or {}).get("content", "")[:300],
            },
            indent=2,
        )
    )


async def time_stream() -> None:
    """Time to first token through the app's own provider, not raw HTTP."""
    from app.llm.base import LLMMessage
    from app.llm.provider import get_llm_provider, resolve_model

    started = time.monotonic()
    first: float | None = None
    chunks = 0
    try:
        async for delta in get_llm_provider().stream_chat(
            system="Be concise.",
            messages=[LLMMessage(role="user", content="Say hello in one sentence.")],
            model=resolve_model(None),
            temperature=0.0,
            max_tokens=256,
        ):
            chunks += 1
            if first is None:
                first = time.monotonic() - started
            print(f"  {time.monotonic() - started:5.2f}s {delta!r}", flush=True)
    except Exception as exc:  # noqa: BLE001 - the failure mode is the finding
        print(f"stream failed: {type(exc).__name__}: {exc}")
    print(
        f"first token: {first:.2f}s" if first else "no tokens",
        f"| chunks: {chunks}",
        f"| total: {time.monotonic() - started:.2f}s",
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", action="store_true", help="list available models")
    parser.add_argument("--stream", action="store_true", help="time the first streamed token")
    parser.add_argument("--agent", help="ping with this agent's real prompt size")
    args = parser.parse_args()

    print(f"provider={settings.llm_provider} base={_base_url()} model={settings.llm_model}\n")
    if args.models:
        await list_models()
    elif args.stream:
        await time_stream()
    else:
        await ping(args.agent)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
