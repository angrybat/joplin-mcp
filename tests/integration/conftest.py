"""
Integration test conftest.

Validates fixture.lock integrity before any test runs.
"""

from __future__ import annotations

import hashlib
import os
import pathlib

import pytest

FIXTURES_ROOT = pathlib.Path(__file__).parent.parent.parent / "fixtures"
LOCK_FILE = FIXTURES_ROOT / "fixture.lock"


def _compute_fixture_checksums() -> dict[str, str]:
    """Return sha256 checksums for generated fixture output files (seed/ + expected/)."""
    checksums: dict[str, str] = {}
    for subdir in ["seed", "expected"]:
        subdir_path = FIXTURES_ROOT / subdir
        if not subdir_path.exists():
            continue
        for path in sorted(subdir_path.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                rel = path.relative_to(FIXTURES_ROOT)
                lock_path = f"fixtures/{rel}".replace("\\", "/")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                checksums[lock_path] = digest
    return checksums


def _parse_lock_file() -> dict[str, str]:
    """Parse fixture.lock into {path: sha256} mapping (skips comment lines)."""
    if not LOCK_FILE.exists():
        return {}
    checksums: dict[str, str] = {}
    for line in LOCK_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            checksum, path = parts
            checksums[path] = checksum
    return checksums


def pytest_configure(config: pytest.Config) -> None:
    """Fail fast if fixture.lock diverges from actual fixture data."""
    # Skip check when running outside the Dagger integration context
    if os.environ.get("SKIP_FIXTURE_LOCK_CHECK"):
        return

    actual = _compute_fixture_checksums()
    locked = _parse_lock_file()

    # A fresh lock file (header comments only) means fixture data not yet generated
    if not locked and not actual:
        return

    if actual != locked:
        added = set(actual) - set(locked)
        removed = set(locked) - set(actual)
        changed = {k for k in actual if k in locked and actual[k] != locked[k]}
        details = []
        if added:
            details.append(f"Added: {sorted(added)}")
        if removed:
            details.append(f"Removed: {sorted(removed)}")
        if changed:
            details.append(f"Changed: {sorted(changed)}")
        raise pytest.UsageError(
            "fixture.lock divergence detected — re-run with --update-lock to regenerate.\n"
            + "\n".join(details)
        )
