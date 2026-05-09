"""Health and readiness helpers for wrapper process."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

from joplin_mcp_wrapper.main import SupervisorState


@dataclass
class ReadinessCache:
    """Caches readiness checks to avoid repeated reachability probes."""

    check_ready: Callable[[], bool]
    cache_seconds: float = 10.0
    now_fn: Callable[[], float] = time.monotonic
    _cached_at: float | None = None
    _cached_ready: bool | None = None

    def is_ready(self) -> bool:
        now = self.now_fn()
        if self._cached_at is not None and self._cached_ready is not None:
            if now - self._cached_at < self.cache_seconds:
                return self._cached_ready

        ready = self.check_ready()
        self._cached_ready = ready
        self._cached_at = now
        return ready


def startup_status(state: SupervisorState) -> tuple[int, dict[str, object]]:
    if state.started_once:
        return 200, {"ok": True, "status": "started"}
    return 503, {"ok": False, "status": "starting"}


def liveness_status(state: SupervisorState) -> tuple[int, dict[str, object]]:
    if state.running:
        return 200, {"ok": True, "status": "alive"}
    return 503, {"ok": False, "status": "down", "last_exit_code": state.last_exit_code}


def readiness_status(cache: ReadinessCache) -> tuple[int, dict[str, object]]:
    ready = cache.is_ready()
    if ready:
        return 200, {"ok": True, "status": "ready"}
    return 503, {"ok": False, "status": "not-ready"}
