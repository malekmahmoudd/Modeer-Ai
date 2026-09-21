"""Regrade unavailable judgments only; preserve the original generation artifact.

Run from backend: python -m tools.rejudge_quality --input ../docs/quality-X.json
--out ../docs/quality-X-rejudged.json. No database access, no answer regeneration.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from app.agents.rubric import judge
from app.core.config import settings
from app.llm.provider import get_llm_provider
from quality_check import build_cases, source_fingerprint


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=1200)
    args = parser.parse_args()
    if args.out.exists() or args.out.resolve() == args.input.resolve():
        parser.error("Use a new output file; original evidence must be preserved")
    if args.max_tokens < 700:
        parser.error("max-tokens must be at least 700")
    original = json.loads(args.input.read_text(encoding="utf-8"))
    current_hash = source_fingerprint()
    if original["generated_with"]["source_sha256"] != current_hash:
        parser.error("Sources differ: do not silently regrade changed evaluation cases")
    cases = {
        (slug, case["id"]): case
        for slug, case in build_cases(list(original["generated_with"]["agents"]))
    }
    provider = get_llm_provider()

    class LargerJudgeBudget:
        async def complete(self, **kwargs):
            kwargs["max_tokens"] = args.max_tokens
            return await provider.complete(**kwargs)

    rows = []
    for row in original["results"]:
        if row.get("judge", {}).get("available") or not row.get("output"):
            continue
        if rows:
            await asyncio.sleep(30)
        case = cases[(row["agent"], row["case"])]
        verdict = await judge(
            case, row["output"], provider=LargerJudgeBudget(), model=original["judge_model"]
        )
        rows.append(
            {
                "agent": row["agent"],
                "case_id": row["case"],
                "sample": row["sample"],
                "judge": verdict.as_dict(),
            }
        )
        print(
            row["agent"],
            row["sample"],
            "available:",
            verdict.available,
            "passed:",
            verdict.passed,
            flush=True,
        )
    report = {
        "source_artifact": args.input.name,
        "source_sha256": current_hash,
        "source_artifact_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "rejudge_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reasoning_effort": settings.llm_reasoning_effort,
        "timeout_seconds": settings.llm_timeout_seconds,
        "provider": settings.llm_provider,
        "judge_model": original["judge_model"],
        "judge_temperature": 0,
        "judge_max_tokens": args.max_tokens,
        "note": "Only unavailable judgments retried. Original answers and scores remain unchanged.",
        "results": rows,
    }
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
