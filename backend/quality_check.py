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
import sys
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
    parser.add_argument("--resume", action="store_true", help="Continue matching .partial results")
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--model", help="Evaluation-only override for every agent")
    parser.add_argument("--out", default="../docs/live-quality-results.json")
    parser.add_argument("--judge-model", default="openai/gpt-oss-120b")
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--pace", type=float, default=PACE_SECONDS)
    args = parser.parse_args()

    if args.samples < 1 or args.pace < 0:
        parser.error("samples must be positive and pace nonnegative")
    cases = [
        (slug, case, sample)
        for sample in range(1, args.samples + 1)
        for slug, case in build_cases(args.agents)
    ]
    out = Path(args.out)
    # Progress goes to a sibling file so an aborted run cannot destroy the last
    # complete one; it is promoted over `out` only when every case has run.
    partial = out.with_suffix(out.suffix + ".partial")
    results: list[dict] = resume_rows(partial, args, cases) if args.resume else []
    completed = len(results)
    aborted = ""

    for index, (slug, case, sample) in enumerate(cases):
        if index < completed:
            continue
        if index:
            await asyncio.sleep(args.pace)
        agent = require_agent(slug).model_copy(deep=True)
        if args.model:
            agent.model.model = args.model
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
            "sample": sample,
            "prompt_version": agent.prompt_version,
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
            judged_ok = judgement.passed if judgement.available else None
        else:
            judged_ok = True

        row["passed"] = None if error or not text else False if not verdict.passed else judged_ok
        results.append(row)

        _write(partial, args, results)
        _print_row(row)

    passed = sum(1 for r in results if r["passed"] is True)
    if aborted:
        print(f"PARTIAL {passed}/{len(results)} of {len(cases)} — kept in {partial}")
        print(f"{out} still holds the last complete run.")
        return 2
    _write(out, args, results)
    partial.unlink(missing_ok=True)
    print(f"\nTOTAL {passed}/{len(results)} — full responses in {out}")
    return 0 if passed == len(results) else 1


def resume_rows(path: Path, args, cases) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        data["model"] != (args.model or settings.llm_model)
        or data["judge_model"] != (None if args.no_judge else args.judge_model)
        or data.get("samples", 1) != args.samples
    ):
        raise ValueError("Resume settings differ from the saved run")
    rows = data["results"]
    if len(rows) > len(cases):
        raise ValueError("Resume case list differs")
    for row, (slug, case, sample) in zip(rows, cases, strict=False):
        agent = require_agent(slug)
        if (
            row["agent"] != slug
            or row["case"] != case["id"]
            or row.get("sample", 1) != sample
            or row["input"] != case["input"]
            or row.get("prompt_version") != agent.prompt_version
            or row["model"] != (args.model or resolve_model(agent.model.model))
        ):
            raise ValueError("Resume case, prompt version or model differs")
    return rows


def summarize(results: list[dict]) -> dict:
    """Separate provider/judge availability from observed answer quality."""
    grouped: dict[str, list[dict]] = {}
    for row in results:
        grouped.setdefault(row["case"], []).append(row)
    summary = {}
    for case, rows in grouped.items():
        valid = [r for r in rows if r["output"] and not r["error"]]
        judged = [r for r in valid if (r.get("judge") or {}).get("available")]
        evaluated = [r for r in valid if r["passed"] is not None]
        summary[case] = {
            "attempts": len(rows),
            "responses": len(valid),
            "provider_errors": len(rows) - len(valid),
            "deterministic_passes": sum(r["review"]["passed"] for r in valid),
            "judge_available": len(judged),
            "judge_passes": sum(r["judge"]["passed"] for r in judged),
            "evaluated": len(evaluated),
            "passes": sum(r["passed"] is True for r in evaluated),
            "pass_rate": (
                sum(r["passed"] is True for r in evaluated) / len(evaluated) if evaluated else None
            ),
        }
    return summary


def _write(path: Path, args, results: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "provider": settings.llm_provider,
                "model": args.model or settings.llm_model,
                "samples": args.samples,
                "summary": summarize(results),
                "judge_model": None if args.no_judge else args.judge_model,
                "results": results,
            },
            indent=2,
        ),
        encoding="utf8",
    )


def _print_row(row: dict) -> None:
    mark = "UNAVAILABLE" if row["passed"] is None else "PASS" if row["passed"] else "FAIL"
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
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(asyncio.run(main()))
