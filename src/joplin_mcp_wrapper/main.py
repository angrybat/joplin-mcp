"""Wrapper entrypoint helpers for joplin-mcp."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os


REQUIRED_ENV_VARS = ("JOPLIN_HOST", "JOPLIN_TOKEN")
DEFAULT_MCP_PORT = 8000


def validate_environment(env: Mapping[str, str] | None = None) -> None:
    """Validate required environment variables for wrapper startup."""
    current_env = env if env is not None else os.environ
    missing = [name for name in REQUIRED_ENV_VARS if not current_env.get(name)]
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Missing required environment variables: {missing_list}")


def _get_int_env(name: str, default: int, env: Mapping[str, str]) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def build_child_command(mcp_port: int) -> list[str]:
    """Build the child command line for streamable HTTP transport."""
    return ["joplin-mcp", "--transport", "streamable-http", "--port", str(mcp_port)]


def build_child_command_from_env(env: Mapping[str, str] | None = None) -> list[str]:
    """Build child command from environment with default MCP port."""
    current_env = env if env is not None else os.environ
    mcp_port = _get_int_env("MCP_PORT", DEFAULT_MCP_PORT, current_env)
    return build_child_command(mcp_port)


@dataclass
class SupervisorState:
    """Tracks child process lifecycle to support health and restart logic."""

    started_once: bool = False
    running: bool = False
    restart_count: int = 0
    last_exit_code: int | None = None

    def on_child_started(self) -> None:
        self.started_once = True
        self.running = True

    def on_child_exited(self, exit_code: int) -> None:
        self.running = False
        self.last_exit_code = exit_code

    def on_child_restarted(self) -> None:
        self.restart_count += 1
        self.running = True
        self.started_once = True


def run() -> int:
    """Project entrypoint configured in pyproject scripts."""
    validate_environment()
    return 0
