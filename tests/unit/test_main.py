"""Unit tests for wrapper runtime helpers."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from joplin_mcp_wrapper.main import validate_environment


def test_validate_environment_rejects_missing_required_config() -> None:
    with pytest.raises(ValueError, match="JOPLIN_HOST, JOPLIN_TOKEN"):
        validate_environment({})
