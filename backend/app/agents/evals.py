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
from app.llm.base import LLMProvider
from app.llm.provider import resolve_model

_DIR = Path(__file__).parent

RUBRIC_DIMENSIONS = [
    "relevance",
    "specialization",
    "usefulness",
    "clarity",
    "personalization",
    "scope_discipline",
    "safety",
]


@dataclass(slots=True)
class CaseResult:
    id: str
    category: str
    passed: bool
    checks: list[str]
    output_preview: str


@dataclass(slots=True)
class AgentEvalReport:
    agent_id: str
    total: int
    passed: int
    results: list[CaseResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return round(self.passed / self.total, 3) if self.total else 0.0


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
        hit = len(output.strip()) > 40
        checks.append(f"{'+' if hit else '-'} substantive length")
        ok = ok and hit

    return ok, checks


async def run_agent(slug: str, provider: LLMProvider) -> AgentEvalReport:
    agent = require_agent(slug)
    cases = load_cases(slug)
    report = AgentEvalReport(agent_id=slug, total=len(cases), passed=0)

    for case in cases:
        packet = build_context(
            agent=agent,
            user=_fake_user(case.get("profile")),
            shared=_fake_mem(case.get("shared_context", [])),
            agent_memory=_fake_mem(case.get("agent_memory", [])),
            goals=[],
            history=[],
            user_message=case["input"],
        )
        result = await provider.complete(
            system=packet.system,
            messages=packet.messages,
            model=resolve_model(agent.model.model),
            temperature=agent.model.temperature,
            max_tokens=agent.model.max_tokens,
        )
        passed, checks = _score(case, result.text)
        report.results.append(
            CaseResult(
                id=case["id"],
                category=case["category"],
                passed=passed,
                checks=checks,
                output_preview=result.text[:160].replace("\n", " "),
            )
        )
        report.passed += int(passed)
    return report


async def run_all(slugs: list[str], provider: LLMProvider) -> list[AgentEvalReport]:
    return [await run_agent(s, provider) for s in slugs]


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Run agent evals")
    parser.add_argument("agents", nargs="*", help="agent slugs (default: all)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    from app.llm.provider import get_llm_provider

    provider = get_llm_provider()
    slugs = args.agents or [a.id for a in all_agents()]
    reports = asyncio.run(run_all(slugs, provider))

    if args.json:
        payload = [
            {
                "agent_id": r.agent_id,
                "pass_rate": r.pass_rate,
                "passed": r.passed,
                "total": r.total,
                "cases": [
                    {"id": c.id, "category": c.category, "passed": c.passed,
                     "checks": c.checks}
                    for c in r.results
                ],
            }
            for r in reports
        ]
        print(json.dumps(payload, indent=2))
    else:
        total_p = total_c = 0
        for r in reports:
            total_p += r.passed
            total_c += r.total
            print(f"\n{r.agent_id:10s}  {r.passed}/{r.total}  ({r.pass_rate:.0%})")
            for c in r.results:
                mark = "PASS" if c.passed else "FAIL"
                print(f"  [{mark}] {c.id} ({c.category})")
                if not c.passed:
                    for chk in c.checks:
                        print(f"         {chk}")
        print(f"\nTOTAL  {total_p}/{total_c}  ({total_p / total_c:.0%})"
              if total_c else "\nNo cases.")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
