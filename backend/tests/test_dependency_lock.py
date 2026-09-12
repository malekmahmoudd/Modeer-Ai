"""The production image installs requirements.lock; the tests must run on it too.

requirements.txt states ranges. The Dockerfile installs requirements.lock —
every package, transitive ones included, pinned with hashes. These checks fail
when the two drift apart, or when the environment running this suite has
different versions from the ones the image will ship: a passing run on
pydantic X says little about an image built with pydantic Y.

To regenerate the lock, see docs/DEPLOYMENT.md, "Backend dependency lock".
"""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

BACKEND = Path(__file__).resolve().parents[1]


def _lock() -> dict[str, str]:
    pins = {}
    for line in (BACKEND / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if match := re.match(r"^([A-Za-z0-9_.-]+)==([^\s\\;]+)", line):
            pins[canonicalize_name(match.group(1))] = match.group(2)
    return pins


def _declared() -> list[Requirement]:
    lines = (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [Requirement(line) for line in (x.split("#")[0].strip() for x in lines) if line]


def test_every_declared_requirement_is_pinned_within_its_range():
    lock = _lock()
    assert len(lock) > len(_declared()), "the lock should include transitive packages"
    for req in _declared():
        name = canonicalize_name(req.name)
        assert name in lock, f"{req.name} is required but not in requirements.lock"
        assert (
            lock[name] in req.specifier
        ), f"requirements.lock pins {req.name}=={lock[name]}, outside {req.specifier}"


def test_every_pin_carries_a_hash():
    text = (BACKEND / "requirements.lock").read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[A-Za-z0-9_.-]+==)", text)
    unhashed = [b.split()[0] for b in blocks if "==" in b.split()[0] and "--hash=" not in b]
    assert not unhashed, f"pins without hashes: {unhashed}"


def test_this_environment_runs_the_locked_versions():
    """Packages the lock names and this environment has must match exactly.

    Absent ones are skipped: uvloop, for one, is Linux-only and never installs
    on a Windows dev machine. Extra ones (pytest, ruff) are test tooling.
    """
    drift = {}
    for name, pinned in _lock().items():
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            continue
        if installed != pinned:
            drift[name] = f"installed {installed}, locked {pinned}"
    assert not drift, f"regenerate the lock or reinstall from it: {drift}"
