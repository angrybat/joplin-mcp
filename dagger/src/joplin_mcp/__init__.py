"""Dagger module package for joplin-mcp."""

import dagger
from dagger import dag, function, object_type


@object_type
class JoplinMcp:

    def _python_container(self, source: dagger.Directory) -> dagger.Container:
        python_version = "3.12.9-slim"
        pip_cache = dag.cache_volume("pip-cache-py312")
        return (
            dag.container()
            .from_(f"python:{python_version}")
            .with_mounted_directory("/workspace", source)
            .with_workdir("/workspace")
            .with_mounted_cache("/root/.cache/pip", pip_cache)
            .with_env_variable("PIP_DISABLE_PIP_VERSION_CHECK", "1")
        )

    async def _python_uv_container(self, source: dagger.Directory) -> dagger.Container:
        uv_cache = dag.cache_volume("uv-cache-py312")
        venv_cache = dag.cache_volume("venv-py312")
        container = (
            self._python_container(source)
            .with_mounted_cache("/root/.cache/uv", uv_cache)
            .with_mounted_cache("/opt/venv", venv_cache)
            .with_env_variable("UV_CACHE_DIR", "/root/.cache/uv")
            .with_env_variable("UV_LINK_MODE", "copy")
            .with_env_variable("VIRTUAL_ENV", "/opt/venv")
            .with_env_variable(
                "PATH",
                "/opt/venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
            )
        )

        uv_exists = await (
            container
            .with_exec(["sh", "-lc", "test -x /opt/venv/bin/uv && printf true || printf false"])
            .stdout()
        )

        if uv_exists.strip() == "true":
            return container

        return (
            container
            .with_exec(["python", "-m", "venv", "/opt/venv"])
            .with_exec(["/opt/venv/bin/python", "-m", "pip", "install", "uv"])
        )

    @function
    async def build_mcp_image(self) -> dagger.Container:
        raise NotImplementedError("build_mcp_image not yet implemented — see PLAN.md Phase 2")

    @function
    async def fixture_data(
        self,
        source: dagger.Directory,
        update_lock: bool = False,
    ) -> dagger.Directory:
        repo = (
            dag.directory()
            .with_directory("fixtures", source.directory("fixtures"))
            .with_directory("src", source.directory("src"))
        )

        return (
            self._python_container(repo)
            .with_exec(
                [
                    "python",
                    "/workspace/src/scripts/generate_fixture_data.py",
                    "--fixtures-root",
                    "/workspace/fixtures",
                    "--output-fixtures-root",
                    "/tmp/fixtures-out",
                    "--update-lock",
                    str(update_lock).lower(),
                ]
            )
            .directory("/tmp/fixtures-out")
        )

    @function
    async def unit_tests(self, source: dagger.Directory, verbosity: int = 0) -> str:
        if verbosity < 0:
            raise ValueError("verbosity must be >= 0")

        capped_verbosity = min(verbosity, 3)
        pytest_args = ["tests/unit", "--color=yes", "-W", "default"]
        if capped_verbosity > 0:
            pytest_args.insert(0, f"-{'v' * capped_verbosity}")

        container = await self._python_uv_container(source)

        return await (
            container
            .with_env_variable("PY_COLORS", "1")
            .with_env_variable("TERM", "xterm-256color")
            .with_exec(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    "python",
                    ".[unit-tests]",
                ]
            )
            .with_exec(["pytest", *pytest_args])
            .stdout()
        )

    @function
    async def postgres_service(self, postgres_version: str) -> dagger.Service:
        raise NotImplementedError("postgres_service not yet implemented — see PLAN.md Phase 3")

    @function
    async def joplin_service(self, joplin_version: str, postgres_version: str) -> dagger.Service:
        raise NotImplementedError("joplin_service not yet implemented — see PLAN.md Phase 4")

    @function
    async def mcp_service(self, joplin_version: str, postgres_version: str) -> dagger.Service:
        raise NotImplementedError("mcp_service not yet implemented — see PLAN.md Phase 5")

    @function
    async def integration_tests(self, joplin_version: str, postgres_version: str) -> str:
        raise NotImplementedError("integration_tests not yet implemented — see PLAN.md Phase 6")

    @function
    async def pre_publish_checks(self) -> str:
        raise NotImplementedError("pre_publish_checks not yet implemented — see PLAN.md Phase 7")

    @function
    async def publish_image(
        self,
        joplin_version: str,
        postgres_version: str,
        version: str,
        registry_username: dagger.Secret,
        registry_password: dagger.Secret,
    ) -> str:
        raise NotImplementedError("publish_image not yet implemented — see PLAN.md Phase 8")

    @function
    async def publish_chart(
        self,
        version: str,
        registry_username: dagger.Secret,
        registry_password: dagger.Secret,
    ) -> str:
        raise NotImplementedError("publish_chart not yet implemented — see PLAN.md Phase 9")