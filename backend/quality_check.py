"""Paced live quality run: synthetic context only, no database writes.

Runs one case per agent against the configured provider and grades the whole
response, not its keywords:

* the deterministic checks in :mod:`app.agents.rubric`, and
* an LLM judge that quotes the span it objects to.

The app itself fails fast on a 429 so a user is never left waiting; this harness
is the opposite case — an unattended run where a rate limit must not be recorded
as a bad answer, so it backs off and retries, and only gives up after that.

    python quality_check.py                       # every agent, default judge
    python quality_check.py --agents writing study
    python quality_check.py --no-judge --out ../docs/quick.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from app.agents.context import build_context
from app.agents.evals import _fake_mem, _fake_user, _score, load_cases
from app.agents.registry import require_agent
from app.agents.rubric import judge, review
from app.core.config import settings
from app.llm.provider import get_llm_provider, resolve_model

DEFAULT_AGENTS = [
    "modeer",
    "study",
    "career",
    "research",
    "writing",
    "travel",
    "shopping",
    "finance",
    "fitness",
    "email",
]
#: Agents whose answers must admit ignorance rather than invent personal facts.
UNKNOWN_FACT_AGENTS = ["study", "career", "writing"]
UNKNOWN_FACT_INPUT = (
    "What is my university, employer, salary, and exam date?"
    " If you do not know, say so. Do not guess."
)

#: Groq's free tier allows a few thousand tokens a minute; 18s between calls
#: keeps a full run inside it.
PACE_SECONDS = 18.0
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF = 65.0
#: Longer than this and the provider is rationing by the day, not the minute.
MAX_WAIT_SECONDS = 180.0


def build_cases(slugs: list[str]) -> list[tuple[str, dict]]:
    cases: list[tuple[str, dict]] = []
    for slug in slugs:
        personalization = next(
            (c for c in load_cases(slug) if c["category"] == "personalization"), None
        )
        if personalization:
            cases.append((slug, personalization))
    for slug in slugs:
        if slug in UNKNOWN_FACT_AGENTS:
            cases.append(
                (
                    slug,
                    {
                        "id": f"{slug}-unknown-facts",
                        "category": "unknown_facts",
                        "input": UNKNOWN_FACT_INPUT,
                        "expect": {"nonempty": True, "max_words": 120},
                    },
                )
            )
    return cases


class QuotaExhausted(RuntimeError):
    """The provider is throttling for longer than a run can usefully wait."""


def _is_rate_limit(exc: Exception) -> bool:
    return "usage limit" in str(exc).lower() or "429" in str(exc)


async def _complete_with_backoff(agent, packet) -> tuple[str, float, str]:
    """Return (text, seconds, error). Retries only rate limits, never bad answers."""
    provider = get_llm_provider()
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        start = time.monotonic()
        try:
            result = await provider.complete(
                system=packet.system,
                messages=packet.messages,
                model=resolve_model(agent.model.model),
                temperature=agent.model.temperature,
                max_tokens=agent.model.max_tokens,
            )
            return result.text, round(time.monotonic() - start, 2), ""
        except Exception as exc:  # noqa: BLE001 - recorded, not raised
            elapsed = round(time.monotonic() - start, 2)
            if not _is_rate_limit(exc) or attempt >= RATE_LIMIT_RETRIES:
                return "", elapsed, f"{type(exc).__name__}: {exc}"
            # A per-minute throttle is worth waiting out. A per-day quota is not:
            # it comes back with a retry-after far beyond any sensible pause, and
            # retrying just burns the rest of the run producing empty rows.
            wait = getattr(exc, "retry_after", None) or RATE_LIMIT_BACKOFF
            if wait > MAX_WAIT_SECONDS:
                raise QuotaExhausted(
                    f"provider asked for a {wait:.0f}s wait — daily quota is likely spent"
                ) from exc
            print(f"    rate limited, waiting {wait:.0f}s", flush=True)
            await asyncio.sleep(wait)
    return "", 0.0, "exhausted rate-limit retries"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", nargs="*", default=DEFAULT_AGENTS)
    parser.add_argument("--out", default="../docs/live-quality-results.json")
    parser.add_argument("--judge-model", default="openai/gpt-oss-120b")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--pace", type=float, default=PACE_SECONDS)
    args = parser.parse_args()

    cases = build_cases(args.agents)
    out = Path(args.out)
    # Progress goes to a sibling file so an aborted run cannot destroy the last
    # complete one; it is promoted over `out` only when every case has run.
    partial = out.with_suffix(out.suffix + ".partial")
    results: list[dict] = []
    aborted = ""

    for index, (slug, case) in enumerate(cases):
        if index:
            await asyncio.sleep(args.pace)
        agent = require_agent(slug)
        packet = build_context(
            agent=agent,
            user=_fake_user(case.get("profile")),
            shared=_fake_mem(case.get("shared_context", [])),
            agent_memory=_fake_mem(case.get("agent_memory", [])),
            goals=[],
            history=[],
            user_message=case["input"],
        )
        try:
            text, seconds, error = await _complete_with_backoff(agent, packet)
        except QuotaExhausted as exc:
            aborted = str(exc)
            print(f"\nABORTED after {len(results)}/{len(cases)} cases: {exc}", flush=True)
            break

        keyword_passed, keyword_checks = _score(case, text)
        verdict = review(case, text)
        row = {
            "agent": slug,
            "case": case["id"],
            "model": resolve_model(agent.model.model),
            "input": case["input"],
            "context": [*case.get("shared_context", []), *case.get("agent_memory", [])],
            "seconds": seconds,
            "error": error,
            "keyword_passed": keyword_passed,
            "keyword_checks": keyword_checks,
            "review": verdict.as_dict(),
            "output": text,
        }

        if not args.no_judge and text and not error:
            await asyncio.sleep(args.pace / 2)
            judgement = await judge(case, text, provider=get_llm_provider(), model=args.judge_model)
            row["judge"] = judgement.as_dict()
            judged_ok = judgement.passed or not judgement.available
        else:
            judged_ok = True

        row["passed"] = bool(text) and not error and verdict.passed and judged_ok
        results.append(row)

        _write(partial, args, results)
        _print_row(row)

    passed = sum(1 for r in results if r["passed"])
    if aborted:
        print(f"PARTIAL {passed}/{len(results)} of {len(cases)} — kept in {partial}")
        print(f"{out} still holds the last complete run.")
        return 2
    _write(out, args, results)
    partial.unlink(missing_ok=True)
    print(f"\nTOTAL {passed}/{len(results)} — full responses in {out}")
    return 0 if passed == len(results) else 1


def _write(path: Path, args, results: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "judge_model": None if args.no_judge else args.judge_model,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf8",
    )


def _print_row(row: dict) -> None:
    mark = "PASS" if row["passed"] else "FAIL"
    print(f"{mark} {row['agent']:9} {row['case']:30} {row['seconds']:>6}s", flush=True)
    if row["error"]:
        print(f"    provider: {row['error']}", flush=True)
    for violation in row["review"]["violations"]:
        evidence = (violation["evidence"] or "").strip().replace("\n", " ")[:90]
        print(f"    rubric: {violation['code']} — {violation['detail']} {evidence}", flush=True)
    judgement = row.get("judge") or {}
    if judgement.get("available"):
        for name, dimension in judgement["dimensions"].items():
            if not dimension["pass"]:
                print(f"    judge: {name} — {dimension['evidence'][:90]}", flush=True)
    elif judgement.get("error"):
        print(f"    judge unavailable: {judgement['error']}", flush=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
