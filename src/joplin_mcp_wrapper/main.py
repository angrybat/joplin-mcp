"""
Joplin MCP Wrapper — entry point.

Supervises the upstream joplin-mcp subprocess and serves Kubernetes health
endpoints on a separate port so probe behavior is independent of MCP transport.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Optional

import uvicorn

from joplin_mcp_wrapper.health import build_health_app, ChildState

logger = logging.getLogger(__name__)

MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8001"))
JOPLIN_HOST = os.environ.get("JOPLIN_HOST", "")
JOPLIN_TOKEN = os.environ.get("JOPLIN_TOKEN", "")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").lower()


def _validate_env() -> None:
    missing = [v for v in ("JOPLIN_HOST", "JOPLIN_TOKEN") if not os.environ.get(v)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)


def _build_child_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "joplin_mcp",
        "--transport",
        "http",
        "--port",
        str(MCP_PORT),
    ]


async def _supervise(state: ChildState) -> None:
    """Start and supervise the joplin-mcp child process."""
    cmd = _build_child_command()
    logger.info("Starting child process: %s", " ".join(cmd))

    env = os.environ.copy()
    env["JOPLIN_HOST"] = JOPLIN_HOST
    env["JOPLIN_TOKEN"] = JOPLIN_TOKEN

    while True:
        proc = subprocess.Popen(cmd, env=env)
        state.pid = proc.pid
        state.started_at = time.monotonic()
        state.healthy = False
        logger.info("Child process started (pid=%d)", proc.pid)

        # Give child a moment to bind before marking startup complete
        await asyncio.sleep(2)
        state.healthy = True
        logger.info("Child process ready (pid=%d)", proc.pid)

        exit_code = await asyncio.get_event_loop().run_in_executor(None, proc.wait)
        state.healthy = False
        state.pid = None
        logger.warning("Child process exited with code %d — restarting in 5s", exit_code)
        await asyncio.sleep(5)


async def _run_health_server(state: ChildState) -> None:
    app = build_health_app(state)
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=HEALTH_PORT,
        log_level=LOG_LEVEL,
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def _main() -> None:
    logging.basicConfig(
        level=LOG_LEVEL.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _validate_env()

    state = ChildState()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: loop.stop())

    await asyncio.gather(
        _supervise(state),
        _run_health_server(state),
    )


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
