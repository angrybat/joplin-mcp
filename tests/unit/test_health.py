"""Unit tests for health and readiness helpers."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from joplin_mcp_wrapper.health import ReadinessCache, liveness_status, readiness_status, startup_status
from joplin_mcp_wrapper.main import SupervisorState


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value


def test_startup_status_is_starting_before_first_start() -> None:
    state = SupervisorState()

    startup_code, startup_payload = startup_status(state)
    assert startup_code == 503
    assert startup_payload["status"] == "starting"


def test_startup_status_is_started_after_first_start() -> None:
    state = SupervisorState()
    state.on_child_started()

    startup_code, startup_payload = startup_status(state)
    assert startup_code == 200
    assert startup_payload["status"] == "started"


def test_liveness_status_is_down_when_not_running() -> None:
    state = SupervisorState()

    live_code, live_payload = liveness_status(state)
    assert live_code == 503
    assert live_payload["status"] == "down"


def test_liveness_status_is_alive_when_running() -> None:
    state = SupervisorState()
    state.on_child_started()

    live_code, live_payload = liveness_status(state)
    assert live_code == 200
    assert live_payload["status"] == "alive"


def test_readiness_status_is_ready_when_probe_passes() -> None:
    cache = ReadinessCache(check_ready=lambda: True)

    ready_code, ready_payload = readiness_status(cache)
    assert ready_code == 200
    assert ready_payload["status"] == "ready"


def test_readiness_status_is_not_ready_when_probe_fails() -> None:
    cache = ReadinessCache(check_ready=lambda: False)

    ready_code, ready_payload = readiness_status(cache)
    assert ready_code == 503
    assert ready_payload["status"] == "not-ready"


def test_readiness_cache_reuses_result_inside_window() -> None:
    clock = FakeClock()
    call_count = 0

    def check_ready() -> bool:
        nonlocal call_count
        call_count += 1
        return True

    cache = ReadinessCache(check_ready=check_ready, cache_seconds=10.0, now_fn=clock.now)

    assert cache.is_ready() is True
    assert cache.is_ready() is True
    assert call_count == 1

    clock.value = 11.0
    assert cache.is_ready() is True
    assert call_count == 2


def test_readiness_cache_reuses_negative_result_inside_window() -> None:
    clock = FakeClock()
    call_count = 0

    def check_ready() -> bool:
        nonlocal call_count
        call_count += 1
        return False

    cache = ReadinessCache(check_ready=check_ready, cache_seconds=10.0, now_fn=clock.now)

    assert cache.is_ready() is False
    assert cache.is_ready() is False
    assert call_count == 1

    clock.value = 11.0
    assert cache.is_ready() is False
    assert call_count == 2
