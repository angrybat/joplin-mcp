"""Unit tests for wrapper runtime helpers."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from joplin_mcp_wrapper.main import (
    SupervisorState,
    build_child_command,
    build_child_command_from_env,
    validate_environment,
)


def test_validate_environment_rejects_missing_required_config() -> None:
    with pytest.raises(ValueError, match="JOPLIN_HOST, JOPLIN_TOKEN"):
        validate_environment({})


def test_build_child_command_uses_streamable_http_and_port() -> None:
    assert build_child_command(8123) == [
        "joplin-mcp",
        "--transport",
        "streamable-http",
        "--port",
        "8123",
    ]


def test_build_child_command_from_env_uses_default_port() -> None:
    assert build_child_command_from_env({})[-1] == "8000"


def test_supervisor_state_defaults() -> None:
    state = SupervisorState()
    assert state.started_once is False
    assert state.running is False
    assert state.restart_count == 0
    assert state.last_exit_code is None


def test_supervisor_state_updates_on_start() -> None:
    state = SupervisorState()

    state.on_child_started()
    assert state.started_once is True
    assert state.running is True
    assert state.restart_count == 0


def test_supervisor_state_updates_on_exit() -> None:
    state = SupervisorState()
    state.on_child_started()

    state.on_child_exited(137)
    assert state.running is False
    assert state.last_exit_code == 137


def test_supervisor_state_updates_on_restart() -> None:
    state = SupervisorState()
    state.on_child_started()
    state.on_child_exited(137)

    state.on_child_restarted()
    assert state.running is True
    assert state.started_once is True
    assert state.restart_count == 1
