"""Find automatic memories stored under the old, fail-open extraction rules.

READ-ONLY. It never writes, deletes or reclassifies anything: what is stored
belongs to the person it describes, a flag here is a question rather than a
verdict, and the keyword backstop produces false positives. The remediation
process is in docs/launch-fixes.md.

Before 2026-09-11 automatic extraction could store, among other things:

  * a sensitive fact the model forgot to flag, or flagged ``false``;
  * a fact under a category outside the prompt's vocabulary;
  * a private note for an unknown specialist, widened into SHARED memory;
  * a Modeer-private note, widened into SHARED memory;
  * a value that overwrote a memory the user had saved by hand.

The first two are detectable and reported here. The last three are not: a
widened note looks exactly like a genuine shared fact, and an overwritten
value is gone from the live database — only a backup taken before the
overwrite still has it.

    python -m tools.memory_audit                 # counts per account
    python -m tools.memory_audit --list          # plus row ids, keys, reasons
    python -m tools.memory_audit --list --values # plus the stored values
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict

from sqlalchemy import select, text

from app.db.models import AgentMemory, SharedMemory
from app.db.session import SessionLocal
from app.memory.sensitivity import looks_sensitive

_CATEGORIES = {
    "education",
    "career",
    "goals",
    "context",
    "preferences",
    "health",
    "finance",
    "routine",
    "targets",
    "weak_topics",
    "general",
}
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
USER_SOURCE = "user"


def _reasons(row) -> list[str]:
    reasons = []
    if not row.sensitive and looks_sensitive(row.key, row.value, category=row.category):
        reasons.append("looks sensitive but is not flagged")
    if row.category not in _CATEGORIES:
        reasons.append(f"unknown category {row.category!r}")
    if not _KEY.match(row.key or ""):
        reasons.append("key outside the current format")
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list each flagged row")
    parser.add_argument(
        "--values", action="store_true", help="include stored values (personal data)"
    )
    args = parser.parse_args()

    findings: dict[str, list[dict]] = defaultdict(list)
    scanned = Counter()
    with SessionLocal() as db:
        if db.bind.dialect.name == "postgresql":
            # Belt and braces: the database itself refuses any write.
            db.execute(text("SET TRANSACTION READ ONLY"))
        try:
            for model, layer in ((SharedMemory, "shared"), (AgentMemory, "agent")):
                for row in db.scalars(select(model)):
                    if row.source == USER_SOURCE:
                        continue  # saved by hand: the user's explicit choice
                    scanned[layer] += 1
                    if reasons := _reasons(row):
                        # Copy plain values now: the rollback below expires every
                        # ORM row, so reading one after the session closes fails.
                        findings[row.user_id].append(
                            {
                                "layer": layer,
                                "owner": getattr(row, "agent_id", None) or "shared",
                                "id": row.id,
                                "category": row.category,
                                "key": row.key,
                                "value": row.value,
                                "reasons": reasons,
                            }
                        )
        finally:
            db.rollback()

    total = sum(len(rows) for rows in findings.values())
    print(
        f"Scanned {scanned['shared']} automatic shared and {scanned['agent']} automatic "
        f"private memories. {total} flagged across {len(findings)} account(s)."
    )
    print("Nothing was changed. See docs/launch-fixes.md for the remediation process.")
    for account, rows in sorted(findings.items()):
        print(f"\naccount {account}: {len(rows)} flagged")
        if not args.list:
            continue
        for found in rows:
            value = f" = {found['value']!r}" if args.values else ""
            print(
                f"  [{found['layer']}:{found['owner']}] {found['id']} "
                f"{found['category']}/{found['key']}{value}"
            )
            for reason in found["reasons"]:
                print(f"      - {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
