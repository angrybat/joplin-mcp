"""
Kubernetes health probe endpoints.

Exposes three probes on a dedicated port, independent of MCP transport:

  GET /startupz  — returns 200 once child process has successfully bound
  GET /livez     — returns 200 while child process is running (process health only)
  GET /readyz    — returns 200 when child is running AND Joplin API is reachable
                   (result is cached for READYZ_CACHE_SECONDS to prevent hammering)
"""

from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logger = logging.getLogger(__name__)

JOPLIN_HOST = os.environ.get("JOPLIN_HOST", "")
JOPLIN_TOKEN = os.environ.get("JOPLIN_TOKEN", "")
READYZ_CACHE_SECONDS = int(os.environ.get("READYZ_CACHE_SECONDS", "10"))
READYZ_TIMEOUT_SECONDS = float(os.environ.get("READYZ_TIMEOUT_SECONDS", "2.0"))


@dataclass
class ChildState:
    """Shared mutable state updated by the supervisor loop."""
    healthy: bool = False
    pid: Optional[int] = None
    started_at: Optional[float] = None
    _readyz_cache: Optional[bool] = field(default=None, repr=False)
    _readyz_cached_at: float = field(default=0.0, repr=False)


async def _joplin_reachable() -> bool:
    url = f"http://{JOPLIN_HOST}/api/ping"
    try:
        async with httpx.AsyncClient(timeout=READYZ_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params={"token": JOPLIN_TOKEN})
            return resp.status_code == 200
    except Exception as exc:
        logger.debug("Joplin reachability check failed: %s", exc)
        return False


def build_health_app(state: ChildState) -> Starlette:

    async def startupz(request: Request) -> JSONResponse:
        """Passes once child has bound. Used by Kubernetes startupProbe."""
        if state.healthy:
            return JSONResponse({"status": "ok", "pid": state.pid}, status_code=200)
        return JSONResponse({"status": "starting"}, status_code=503)

    async def livez(request: Request) -> JSONResponse:
        """Process-health only. No outbound checks. Used by Kubernetes livenessProbe."""
        if state.healthy and state.pid is not None:
            return JSONResponse({"status": "ok", "pid": state.pid}, status_code=200)
        return JSONResponse({"status": "unhealthy"}, status_code=503)

    async def readyz(request: Request) -> JSONResponse:
        """Includes cached Joplin API check. Used by Kubernetes readinessProbe."""
        if not state.healthy:
            return JSONResponse({"status": "not_ready", "reason": "child_not_running"}, status_code=503)

        now = time.monotonic()
        if now - state._readyz_cached_at > READYZ_CACHE_SECONDS:
            state._readyz_cache = await _joplin_reachable()
            state._readyz_cached_at = now

        if state._readyz_cache:
            return JSONResponse({"status": "ok"}, status_code=200)
        return JSONResponse({"status": "not_ready", "reason": "joplin_unreachable"}, status_code=503)

    return Starlette(routes=[
        Route("/startupz", startupz),
        Route("/livez", livez),
        Route("/readyz", readyz),
    ])
