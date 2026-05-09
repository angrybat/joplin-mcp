"""Wrapper entrypoint helpers for joplin-mcp."""

from __future__ import annotations

from collections.abc import Mapping
import os


REQUIRED_ENV_VARS = ("JOPLIN_HOST", "JOPLIN_TOKEN")


def validate_environment(env: Mapping[str, str] | None = None) -> None:
    """Validate required environment variables for wrapper startup."""
    current_env = env if env is not None else os.environ
    missing = [name for name in REQUIRED_ENV_VARS if not current_env.get(name)]
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Missing required environment variables: {missing_list}")


def run() -> int:
    """Project entrypoint configured in pyproject scripts."""
    validate_environment()
    return 0
