"""Wrapper entrypoint helpers for joplin-mcp."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
import subprocess
import threading
import time
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from joplin_mcp_wrapper.health import ReadinessCache, liveness_status, readiness_status, startup_status


REQUIRED_ENV_VARS = ("JOPLIN_HOST", "JOPLIN_TOKEN")
DEFAULT_MCP_PORT = 8000
DEFAULT_HEALTH_PORT = 8001
DEFAULT_READYZ_CACHE_SECONDS = 10.0
DEFAULT_READYZ_TIMEOUT_SECONDS = 2.0


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


def _get_float_env(name: str, default: float, env: Mapping[str, str]) -> float:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def build_child_command(mcp_port: int) -> list[str]:
    """Build the child command line for streamable HTTP transport."""
    return ["joplin-mcp", "--transport", "streamable-http", "--port", str(mcp_port)]


def build_child_command_from_env(env: Mapping[str, str] | None = None) -> list[str]:
    """Build child command from environment with default MCP port."""
    current_env = env if env is not None else os.environ
    mcp_port = _get_int_env("MCP_PORT", DEFAULT_MCP_PORT, current_env)
    return build_child_command(mcp_port)


def check_joplin_reachable(joplin_host: str, joplin_token: str, timeout_seconds: float) -> bool:
    base = joplin_host.rstrip("/")
    query = urllib_parse.urlencode({"token": joplin_token})
    url = f"{base}/api/ping?{query}"

    try:
        with urllib_request.urlopen(url, timeout=timeout_seconds) as response:
            return 200 <= response.status < 400
    except (urllib_error.URLError, TimeoutError, OSError):
        return False


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


def create_health_app(state: SupervisorState, readiness_cache: ReadinessCache) -> Starlette:
    async def startupz(_: object) -> JSONResponse:
        code, payload = startup_status(state)
        return JSONResponse(payload, status_code=code)

    async def livez(_: object) -> JSONResponse:
        code, payload = liveness_status(state)
        return JSONResponse(payload, status_code=code)

    async def readyz(_: object) -> JSONResponse:
        code, payload = readiness_status(readiness_cache)
        return JSONResponse(payload, status_code=code)

    return Starlette(
        routes=[
            Route("/startupz", startupz, methods=["GET"]),
            Route("/livez", livez, methods=["GET"]),
            Route("/readyz", readyz, methods=["GET"]),
        ]
    )


def run() -> int:
    """Project entrypoint configured in pyproject scripts."""
    validate_environment()
    current_env = dict(os.environ)

    health_port = _get_int_env("HEALTH_PORT", DEFAULT_HEALTH_PORT, current_env)
    readyz_cache_seconds = _get_float_env(
        "READYZ_CACHE_SECONDS",
        DEFAULT_READYZ_CACHE_SECONDS,
        current_env,
    )
    readyz_timeout_seconds = _get_float_env(
        "READYZ_TIMEOUT_SECONDS",
        DEFAULT_READYZ_TIMEOUT_SECONDS,
        current_env,
    )

    state = SupervisorState()
    readiness_cache = ReadinessCache(
        check_ready=lambda: check_joplin_reachable(
            current_env["JOPLIN_HOST"],
            current_env["JOPLIN_TOKEN"],
            readyz_timeout_seconds,
        ),
        cache_seconds=readyz_cache_seconds,
    )
    health_app = create_health_app(state, readiness_cache)

    config = uvicorn.Config(
        health_app,
        host="0.0.0.0",
        port=health_port,
        access_log=False,
        log_level="warning",
    )
    health_server = uvicorn.Server(config)
    health_thread = threading.Thread(target=health_server.run, daemon=True)
    health_thread.start()

    for _ in range(100):
        if health_server.started:
            break
        time.sleep(0.05)

    child_command = build_child_command_from_env(current_env)
    child = subprocess.Popen(child_command, env=current_env)
    state.on_child_started()

    try:
        exit_code = child.wait()
        state.on_child_exited(exit_code)
    finally:
        health_server.should_exit = True
        health_thread.join(timeout=5)

    return state.last_exit_code if state.last_exit_code is not None else 1
