"""Consistent SQLite snapshot; refuses to overwrite an existing backup."""
import argparse
import sqlite3
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("destination", type=Path)
args = parser.parse_args()
source = args.source.resolve(strict=True)
target = args.destination.resolve()
target.parent.mkdir(parents=True, exist_ok=True)
with target.open("xb"):
    pass
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup integrity check failed")
print("Snapshot created and integrity checked.")
