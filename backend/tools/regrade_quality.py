"""Regrade saved synthetic responses without spending generation quota again.
Run from backend: python -m tools.regrade_quality INPUT OUTPUT --pace 8
Original responses and original grades remain in INPUT unchanged.
"""

import argparse
import asyncio
import json
from pathlib import Path

from app.agents.evals import _fake_user
from app.agents.rubric import judge, review
from app.llm.provider import get_llm_provider
from quality_check import DEFAULT_AGENTS, build_cases, summarize


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--judge-model", default="qwen/qwen3.8-27b")
    parser.add_argument("--pace", type=float, default=8)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("Write to a new report to preserve original evidence")
    data = json.loads(args.input.read_text(encoding="utf-8"))
    cases = {case["id"]: case for _, case in build_cases(DEFAULT_AGENTS)}
    rows = []
    partial = args.output.with_suffix(args.output.suffix + ".partial")
    provider = get_llm_provider()
    for original in data["results"]:
        case = cases[original["case"]]
        if original["input"] != case["input"]:
            raise ValueError("Saved case differs from fixture")
        case = {**case, "display_name": _fake_user(case.get("profile")).display_name}
        row = {**original, "display_name": case["display_name"], "profile": case.get("profile", {})}
        row["review"] = review(case, row["output"]).as_dict()
        if row["output"] and not row["error"]:
            verdict = await judge(case, row["output"], provider=provider, model=args.judge_model)
            row["judge"] = verdict.as_dict()
            row["passed"] = (
                False
                if not row["review"]["passed"]
                else verdict.passed
                if verdict.available
                else None
            )
        else:
            row["passed"] = None
        rows.append(row)
        report = {
            **data,
            "judge_version": 2,
            "judge_model": args.judge_model,
            "regraded_existing_responses": True,
            "source_report": args.input.name,
            "results": rows,
            "summary": summarize(rows),
        }
        partial.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(row["agent"], row.get("sample", 1), row["passed"], flush=True)
        await asyncio.sleep(args.pace)
    partial.replace(args.output)
    print(f"TOTAL {sum(r['passed'] is True for r in rows)}/{len(rows)}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
