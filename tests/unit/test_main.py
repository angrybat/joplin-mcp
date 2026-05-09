"""Unit tests for wrapper runtime helpers."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest import mock

import pytest
from starlette.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from joplin_mcp_wrapper.main import (
    SupervisorState,
    _get_int_env,
    _get_float_env,
    build_child_command,
    build_child_command_from_env,
    check_joplin_reachable,
    create_health_app,
    run,
    validate_environment,
)
from joplin_mcp_wrapper.health import ReadinessCache


class TestValidateEnvironment:
    def test_rejects_when_both_required_vars_missing(self) -> None:
        with pytest.raises(ValueError, match="JOPLIN_HOST, JOPLIN_TOKEN"):
            validate_environment({})

    def test_rejects_when_joplin_host_missing(self) -> None:
        with pytest.raises(ValueError, match="JOPLIN_HOST"):
            validate_environment({"JOPLIN_TOKEN": "tok"})

    def test_rejects_when_joplin_token_missing(self) -> None:
        with pytest.raises(ValueError, match="JOPLIN_TOKEN"):
            validate_environment({"JOPLIN_HOST": "http://joplin:22300"})

    def test_passes_when_both_required_vars_present(self) -> None:
        validate_environment({"JOPLIN_HOST": "http://joplin:22300", "JOPLIN_TOKEN": "tok"})

    def test_uses_os_environ_when_env_is_none(self) -> None:
        with mock.patch.dict("os.environ", {"JOPLIN_HOST": "http://h", "JOPLIN_TOKEN": "t"}):
            validate_environment(None)


class TestGetIntEnv:
    def test_returns_default_for_missing_key(self) -> None:
        assert _get_int_env("MCP_PORT", 8000, {}) == 8000

    def test_returns_default_for_empty_string(self) -> None:
        assert _get_int_env("MCP_PORT", 8000, {"MCP_PORT": ""}) == 8000

    def test_returns_parsed_int_for_explicit_value(self) -> None:
        assert _get_int_env("MCP_PORT", 8000, {"MCP_PORT": "9090"}) == 9090


class TestGetFloatEnv:
    def test_returns_default_for_missing_key(self) -> None:
        assert _get_float_env("READYZ_TIMEOUT_SECONDS", 2.0, {}) == 2.0

    def test_returns_default_for_empty_string(self) -> None:
        assert _get_float_env("READYZ_TIMEOUT_SECONDS", 2.0, {"READYZ_TIMEOUT_SECONDS": ""}) == 2.0

    def test_returns_parsed_float_for_explicit_value(self) -> None:
        assert _get_float_env("READYZ_TIMEOUT_SECONDS", 2.0, {"READYZ_TIMEOUT_SECONDS": "1.25"}) == 1.25


class TestBuildChildCommand:
    def test_builds_correct_command_with_given_port(self) -> None:
        assert build_child_command(8123) == [
            "joplin-mcp",
            "--transport",
            "streamable-http",
            "--port",
            "8123",
        ]

    def test_port_is_always_a_string(self) -> None:
        cmd = build_child_command(9000)
        assert cmd[-1] == "9000"
        assert isinstance(cmd[-1], str)


class TestBuildChildCommandFromEnv:
    def test_uses_default_port_when_mcp_port_not_in_env(self) -> None:
        assert build_child_command_from_env({})[-1] == "8000"

    def test_uses_explicit_mcp_port_from_env(self) -> None:
        assert build_child_command_from_env({"MCP_PORT": "9090"})[-1] == "9090"

    def test_uses_os_environ_when_env_is_none(self) -> None:
        with mock.patch.dict("os.environ", {"MCP_PORT": "7777"}):
            assert build_child_command_from_env(None)[-1] == "7777"


class TestCheckJoplinReachable:
    def test_returns_true_for_200_response(self) -> None:
        fake = mock.MagicMock()
        fake.__enter__.return_value.status = 200
        with mock.patch("joplin_mcp_wrapper.main.urllib_request.urlopen", return_value=fake):
            assert check_joplin_reachable("http://joplin:22300", "tok", 0.5) is True

    def test_returns_true_for_3xx_response(self) -> None:
        fake = mock.MagicMock()
        fake.__enter__.return_value.status = 302
        with mock.patch("joplin_mcp_wrapper.main.urllib_request.urlopen", return_value=fake):
            assert check_joplin_reachable("http://joplin:22300", "tok", 0.5) is True

    def test_returns_false_for_4xx_response(self) -> None:
        fake = mock.MagicMock()
        fake.__enter__.return_value.status = 404
        with mock.patch("joplin_mcp_wrapper.main.urllib_request.urlopen", return_value=fake):
            assert check_joplin_reachable("http://joplin:22300", "tok", 0.5) is False

    def test_returns_false_on_url_error(self) -> None:
        import urllib.error
        with mock.patch(
            "joplin_mcp_wrapper.main.urllib_request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            assert check_joplin_reachable("http://joplin:22300", "tok", 0.5) is False

    def test_returns_false_on_os_error(self) -> None:
        with mock.patch(
            "joplin_mcp_wrapper.main.urllib_request.urlopen",
            side_effect=OSError("network unreachable"),
        ):
            assert check_joplin_reachable("http://joplin:22300", "tok", 0.5) is False

    def test_builds_url_with_token_query_param(self) -> None:
        fake = mock.MagicMock()
        fake.__enter__.return_value.status = 200
        with mock.patch(
            "joplin_mcp_wrapper.main.urllib_request.urlopen", return_value=fake
        ) as patched:
            check_joplin_reachable("http://joplin:22300/", "mytoken", 0.5)
            url = patched.call_args[0][0]
        assert "token=mytoken" in url
        assert url.startswith("http://joplin:22300/api/ping")


class TestSupervisorState:
    def test_defaults_are_all_falsy_or_none(self) -> None:
        state = SupervisorState()
        assert state.started_once is False
        assert state.running is False
        assert state.restart_count == 0
        assert state.last_exit_code is None

    def test_on_child_started_marks_started_and_running(self) -> None:
        state = SupervisorState()
        state.on_child_started()
        assert state.started_once is True
        assert state.running is True
        assert state.restart_count == 0

    def test_on_child_exited_marks_not_running_and_records_exit_code(self) -> None:
        state = SupervisorState()
        state.on_child_started()
        state.on_child_exited(137)
        assert state.running is False
        assert state.last_exit_code == 137

    def test_on_child_restarted_increments_count_and_marks_running(self) -> None:
        state = SupervisorState()
        state.on_child_started()
        state.on_child_exited(137)
        state.on_child_restarted()
        assert state.running is True
        assert state.started_once is True
        assert state.restart_count == 1

    def test_restart_count_accumulates_across_multiple_restarts(self) -> None:
        state = SupervisorState()
        state.on_child_started()
        for i in range(3):
            state.on_child_exited(1)
            state.on_child_restarted()
        assert state.restart_count == 3


class TestCreateHealthApp:
    def test_exposes_startupz_livez_readyz_routes(self) -> None:
        app = create_health_app(SupervisorState(), ReadinessCache(check_ready=lambda: True))
        paths = sorted(route.path for route in app.routes)
        assert paths == ["/livez", "/readyz", "/startupz"]

    def test_startupz_returns_503_before_child_starts(self) -> None:
        app = create_health_app(SupervisorState(), ReadinessCache(check_ready=lambda: True))
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/startupz")
        assert resp.status_code == 503

    def test_startupz_returns_200_after_child_starts(self) -> None:
        state = SupervisorState()
        state.on_child_started()
        app = create_health_app(state, ReadinessCache(check_ready=lambda: True))
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/startupz")
        assert resp.status_code == 200

    def test_livez_returns_503_when_child_not_running(self) -> None:
        app = create_health_app(SupervisorState(), ReadinessCache(check_ready=lambda: True))
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/livez")
        assert resp.status_code == 503

    def test_livez_returns_200_when_child_running(self) -> None:
        state = SupervisorState()
        state.on_child_started()
        app = create_health_app(state, ReadinessCache(check_ready=lambda: True))
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/livez")
        assert resp.status_code == 200

    def test_readyz_returns_200_when_probe_passes(self) -> None:
        app = create_health_app(SupervisorState(), ReadinessCache(check_ready=lambda: True))
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/readyz")
        assert resp.status_code == 200

    def test_readyz_returns_503_when_probe_fails(self) -> None:
        app = create_health_app(SupervisorState(), ReadinessCache(check_ready=lambda: False))
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/readyz")
        assert resp.status_code == 503

    def test_probe_responses_are_json(self) -> None:
        state = SupervisorState()
        state.on_child_started()
        app = create_health_app(state, ReadinessCache(check_ready=lambda: True))
        with TestClient(app, raise_server_exceptions=False) as client:
            for path in ("/startupz", "/livez", "/readyz"):
                resp = client.get(path)
                assert resp.headers["content-type"].startswith("application/json"), path
                assert "ok" in resp.json(), path


class TestRun:
    def _make_mock_server(self, started: bool = True) -> mock.MagicMock:
        server = mock.MagicMock()
        server.started = started
        server.run = mock.MagicMock()
        server.should_exit = False
        return server

    def _make_mock_process(self, exit_code: int = 0) -> mock.MagicMock:
        proc = mock.MagicMock()
        proc.wait.return_value = exit_code
        return proc

    def test_raises_when_required_env_vars_missing(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="JOPLIN_HOST"):
                run()

    def test_returns_child_exit_code(self) -> None:
        env = {"JOPLIN_HOST": "http://joplin:22300", "JOPLIN_TOKEN": "tok"}
        server = self._make_mock_server(started=True)
        proc = self._make_mock_process(exit_code=42)

        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch("joplin_mcp_wrapper.main.uvicorn.Config"), \
             mock.patch("joplin_mcp_wrapper.main.uvicorn.Server", return_value=server), \
             mock.patch("joplin_mcp_wrapper.main.threading.Thread") as mock_thread, \
             mock.patch("joplin_mcp_wrapper.main.subprocess.Popen", return_value=proc):
            mock_thread.return_value.start = mock.MagicMock()
            result = run()

        assert result == 42

    def test_starts_child_with_correct_command(self) -> None:
        env = {"JOPLIN_HOST": "http://joplin:22300", "JOPLIN_TOKEN": "tok"}
        server = self._make_mock_server(started=True)
        proc = self._make_mock_process(exit_code=0)

        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch("joplin_mcp_wrapper.main.uvicorn.Config"), \
             mock.patch("joplin_mcp_wrapper.main.uvicorn.Server", return_value=server), \
             mock.patch("joplin_mcp_wrapper.main.threading.Thread") as mock_thread, \
             mock.patch("joplin_mcp_wrapper.main.subprocess.Popen", return_value=proc) as mock_popen:
            mock_thread.return_value.start = mock.MagicMock()
            run()

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "joplin-mcp"
        assert "--transport" in cmd
        assert "streamable-http" in cmd

    def test_uses_health_port_from_env(self) -> None:
        env = {
            "JOPLIN_HOST": "http://joplin:22300",
            "JOPLIN_TOKEN": "tok",
            "HEALTH_PORT": "9999",
        }
        server = self._make_mock_server(started=True)
        proc = self._make_mock_process(exit_code=0)
        captured_config: dict = {}

        def fake_config(app, **kwargs):
            captured_config.update(kwargs)
            return mock.MagicMock()

        with mock.patch.dict("os.environ", env, clear=True), \
             mock.patch("joplin_mcp_wrapper.main.uvicorn.Config", side_effect=fake_config), \
             mock.patch("joplin_mcp_wrapper.main.uvicorn.Server", return_value=server), \
             mock.patch("joplin_mcp_wrapper.main.threading.Thread") as mock_thread, \
             mock.patch("joplin_mcp_wrapper.main.subprocess.Popen", return_value=proc):
            mock_thread.return_value.start = mock.MagicMock()
            run()

        assert captured_config["port"] == 9999
