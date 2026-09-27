"""Agent evaluation harness.

Fixtures live next to each agent in ``evals.json``. Every agent covers the same
case categories:

    in_domain · ambiguous · out_of_domain · personalization ·
    bad_assumption · safety · quality

Scoring is deterministic and heuristic (substring / redirect / clarifying-question
checks) so it runs in CI against the mock provider. Point it at a real provider
for a qualitative pass:

    python -m app.agents.evals                # all agents, mock provider
    python -m app.agents.evals study career   # selected agents
    python -m app.agents.evals --json         # machine-readable
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from app.agents.context import build_context
from app.agents.registry import all_agents, require_agent
from app.agents.rubric import RUBRIC_DIMENSIONS, review
from app.llm.base import LLMProvider
from app.llm.provider import resolve_model

#: A per-minute throttle is waited out; a wait longer than this means the daily
#: quota is spent, and the remaining cases are skipped rather than failed.
RATE_LIMIT_RETRIES = 3
RATE_LIMIT_BACKOFF = 65.0
MAX_WAIT_SECONDS = 180.0


class QuotaSpent(RuntimeError):
    """The provider is rationing by the day; nothing more will be answered."""


def _is_rate_limit(exc: Exception) -> bool:
    return "usage limit" in str(exc).lower() or "429" in str(exc)


async def _complete(provider, **kwargs):
    """One completion, waiting out per-minute rate limits (never bad answers)."""
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            return await provider.complete(**kwargs)
        except Exception as exc:
            if not _is_rate_limit(exc) or attempt >= RATE_LIMIT_RETRIES:
                raise
            wait = getattr(exc, "retry_after", None) or RATE_LIMIT_BACKOFF
            if wait > MAX_WAIT_SECONDS:
                raise QuotaSpent(f"provider asked for a {wait:.0f}s wait") from exc
            print(f"    rate limited, waiting {wait:.0f}s", file=sys.stderr, flush=True)
            await asyncio.sleep(wait)
    raise RuntimeError("unreachable")


_quota_spent = False

__all__ = ["RUBRIC_DIMENSIONS", "AgentEvalReport", "CaseResult", "load_cases", "run_agent"]

_DIR = Path(__file__).parent


@dataclass(slots=True)
class CaseResult:
    id: str
    category: str
    passed: bool
    checks: list[str]
    output_preview: str
    #: Not run: the provider's daily quota was spent. Not a failed answer.
    skipped: bool = False


@dataclass(slots=True)
class AgentEvalReport:
    agent_id: str
    total: int
    passed: int
    results: list[CaseResult] = field(default_factory=list)

    @property
    def answered(self) -> int:
        return sum(1 for r in self.results if not r.skipped)

    @property
    def pass_rate(self) -> float:
        """Of the cases that got an answer: a spent quota is not a failure."""
        return round(self.passed / self.answered, 3) if self.answered else 0.0


def load_cases(slug: str) -> list[dict]:
    path = _DIR / slug / "evals.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("cases", [])


def _fake_user(profile: dict | None = None):
    return SimpleNamespace(
        display_name="Alex",
        profile=profile or {},
        onboarded=True,
        id="eval-user",
    )


def _fake_mem(rows: list[dict]):
    return [
        SimpleNamespace(
            category=r.get("category", "general"),
            key=r["key"],
            value=r["value"],
        )
        for r in rows
    ]


def _score(case: dict, output: str) -> tuple[bool, list[str]]:
    text = output.lower()
    checks: list[str] = []
    ok = True
    expect = case.get("expect", {})

    mentions_any = expect.get("mentions_any", [])
    if mentions_any:
        any_hit = any(n.lower() in text for n in mentions_any)
        shown = " / ".join(f"'{n}'" for n in mentions_any)
        checks.append(f"{'+' if any_hit else '-'} mentions one of {shown}")
        ok = ok and any_hit

    for needle in expect.get("mentions_all", []):
        hit = needle.lower() in text
        checks.append(f"{'+' if hit else '-'} mentions '{needle}'")
        ok = ok and hit

    for needle in expect.get("not_mentions", []):
        miss = needle.lower() not in text
        checks.append(f"{'+' if miss else '-'} avoids '{needle}'")
        ok = ok and miss

    redirect = expect.get("redirects_to")
    if redirect:
        target = require_agent(redirect)
        hit = (
            target.name.lower() in text
            or redirect.lower() in text
            or "specialist" in text
            or "agent" in text
        )
        checks.append(f"{'+' if hit else '-'} redirects toward {target.name}")
        ok = ok and hit

    if expect.get("asks_clarifying"):
        hit = "?" in output
        checks.append(f"{'+' if hit else '-'} asks a clarifying question")
        ok = ok and hit

    if expect.get("nonempty", True):
        hit = bool(output.strip())
        checks.append(f"{'+' if hit else '-'} nonempty response")
        ok = ok and hit

    return ok, checks


async def run_agent(
    slug: str,
    provider: LLMProvider,
    *,
    delay: float = 0.0,
    strict: bool = False,
) -> AgentEvalReport:
    """Run one agent's fixtures.

    ``strict`` adds the deterministic quality checks from :mod:`app.agents.rubric`
    on top of the keyword scoring. It is off by default because the mock provider
    returns a canned preview rather than a real answer, so those checks only mean
    something against a live model.
    """
    agent = require_agent(slug)
    cases = load_cases(slug)
    report = AgentEvalReport(agent_id=slug, total=len(cases), passed=0)

    global _quota_spent
    for i, case in enumerate(cases):
        if _quota_spent:
            report.results.append(
                CaseResult(
                    id=case["id"],
                    category=case["category"],
                    passed=False,
                    checks=["~ skipped: the provider's daily quota is spent"],
                    output_preview="",
                    skipped=True,
                )
            )
            continue
        if i and delay:
            await asyncio.sleep(delay)
        packet = build_context(
            agent=agent,
            user=_fake_user(case.get("profile")),
            shared=_fake_mem(case.get("shared_context", [])),
            agent_memory=_fake_mem(case.get("agent_memory", [])),
            goals=[],
            history=[],
            user_message=case["input"],
        )
        provider_failed = False
        try:
            result = await _complete(
                provider,
                system=packet.system,
                messages=packet.messages,
                model=resolve_model(agent.model.model),
                temperature=agent.model.temperature,
                max_tokens=agent.model.max_tokens,
            )
            text = result.text
        except QuotaSpent:
            _quota_spent = True
            report.results.append(
                CaseResult(
                    id=case["id"],
                    category=case["category"],
                    passed=False,
                    checks=["~ skipped: the provider's daily quota is spent"],
                    output_preview="",
                    skipped=True,
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - record and keep going
            provider_failed = True
            text = f"[provider error: {type(exc).__name__}]"
        passed, checks = _score(case, text)
        if strict and not provider_failed:
            verdict = review(case, text)
            checks.extend(str(v) for v in verdict.violations)
            passed = passed and verdict.passed
        if provider_failed:
            passed = False
            checks.append("- provider request failed")
        report.results.append(
            CaseResult(
                id=case["id"],
                category=case["category"],
                passed=passed,
                checks=checks,
                output_preview=text[:200].replace("\n", " "),
            )
        )
        report.passed += int(passed)
    return report


async def run_all(
    slugs: list[str], provider: LLMProvider, *, delay: float = 0.0, strict: bool = False
) -> list[AgentEvalReport]:
    return [await run_agent(s, provider, delay=delay, strict=strict) for s in slugs]


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Run agent evals")
    parser.add_argument("agents", nargs="*", help="agent slugs (default: all)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds between cases (throttle rate-limited providers)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="print each response preview",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="also apply the quality rubric (meaningful only against a real provider)",
    )
    args = parser.parse_args()

    from app.llm.provider import get_llm_provider

    provider = get_llm_provider()
    slugs = args.agents or [a.id for a in all_agents()]
    reports = asyncio.run(run_all(slugs, provider, delay=args.delay, strict=args.strict))

    if args.json:
        payload = [
            {
                "agent_id": r.agent_id,
                "pass_rate": r.pass_rate,
                "passed": r.passed,
                "total": r.total,
                "cases": [
                    {"id": c.id, "category": c.category, "passed": c.passed, "checks": c.checks}
                    for c in r.results
                ],
            }
            for r in reports
        ]
        print(json.dumps(payload, indent=2))
    else:
        total_p = total_c = skipped = 0
        for r in reports:
            total_p += r.passed
            total_c += r.answered
            skipped += r.total - r.answered
            print(f"\n{r.agent_id:10s}  {r.passed}/{r.answered}  ({r.pass_rate:.0%})")
            for c in r.results:
                mark = "SKIP" if c.skipped else "PASS" if c.passed else "FAIL"
                print(f"  [{mark}] {c.id} ({c.category})")
                if not c.passed or c.skipped:
                    for chk in c.checks:
                        print(f"         {chk}")
                if args.show:
                    print(f"         > {c.output_preview}")
        print(
            f"\nTOTAL  {total_p}/{total_c}  ({total_p / total_c:.0%})" if total_c else "\nNo cases."
        )
        if skipped:
            print(f"SKIPPED  {skipped} (daily quota spent; rerun these agents later)")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
