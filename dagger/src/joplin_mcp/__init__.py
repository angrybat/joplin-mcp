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

    async def _python_test_container(self, source: dagger.Directory) -> dagger.Container:
        container = await self._python_uv_container(source)
        return (
            container
            .with_exec(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    "python",
                    ".[tests]",
                ]
            )
        )

    @function
    async def build_mcp_image(
        self,
        source: dagger.Directory,
    ) -> dagger.Container:
        repo = (
            dag.directory()
            .with_file("LICENSE", source.file("LICENSE"))
            .with_file("README.md", source.file("README.md"))
            .with_file("pyproject.toml", source.file("pyproject.toml"))
            .with_directory("src", source.directory("src"))
        )

        build_container = await self._python_uv_container(repo)
        return ( 
            build_container.with_exec([
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    "python",
                    ".",
            ])
            .with_env_variable("VIRTUAL_ENV", "/opt/venv")
            .with_env_variable(
                "PATH",
                "/opt/venv/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
            )
            .with_workdir("/app")
            .with_entrypoint(["joplin-mcp-wrapper"])
            .with_exposed_port(8000)
            .with_exposed_port(8001)
        )

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

        container = await self._python_test_container(source)

        return await (
            container
            .with_env_variable("PY_COLORS", "1")
            .with_env_variable("TERM", "xterm-256color")
            .with_exec(["pytest", *pytest_args])
            .stdout()
        )

    @function
    async def postgres_service(
        self,
        postgres_version: str = "16",
    ) -> dagger.Service:
        return (
            dag.container()
            .from_(f"postgres:{postgres_version}")
            .with_env_variable("POSTGRES_HOST_AUTH_METHOD", "trust")
            .with_env_variable("POSTGRES_DB", "postgres")
            .with_exposed_port(5432)
            .as_service()
        )

    @function
    async def joplin_service(
        self,
        source: dagger.Directory,
        joplin_version: str,
        postgres_version: str,
    ) -> dagger.Service:
        repo = (
            dag.directory()
            .with_file("LICENSE", source.file("LICENSE"))
            .with_file("README.md", source.file("README.md"))
            .with_file("pyproject.toml", source.file("pyproject.toml"))
            .with_directory("fixtures", source.directory("fixtures"))
            .with_directory("src", source.directory("src"))
            .with_directory("tests", source.directory("tests"))
        )
        postgres = await self.postgres_service(postgres_version=postgres_version)

        joplin_service = (
            dag.container()
            .from_(f"joplin/server:{joplin_version}")
            .with_service_binding("postgres", postgres)
            .with_env_variable("APP_PORT", "22300")
            .with_env_variable("APP_BASE_URL", "http://joplin:22300")
            .with_env_variable("DB_CLIENT", "pg")
            .with_env_variable("POSTGRES_HOST", "postgres")
            .with_env_variable("POSTGRES_PORT", "5432")
            .with_env_variable("POSTGRES_DATABASE", "postgres")
            .with_env_variable("POSTGRES_USER", "postgres")
            .with_env_variable("POSTGRES_PASSWORD", "")
            .with_exposed_port(22300)
            .as_service()
        )

        await (
            self._python_container(repo)
            .with_env_variable("PYTHONUNBUFFERED", "1")
            .with_service_binding("joplin", joplin_service)
            .with_exec(
                [
                    "python",
                    "/workspace/src/scripts/seed_joplin_api.py",
                    "--fixtures-root",
                    "/workspace/fixtures",
                    "--joplin-base-url",
                    "http://joplin:22300",
                    "--admin-email",
                    "admin@localhost",
                    "--admin-password",
                    "admin",
                ]
            )
            .stdout()
        )

        await (
            (await self._python_test_container(repo))
            .with_env_variable("PYTHONUNBUFFERED", "1")
            .with_service_binding("joplin", joplin_service)
            .with_env_variable("JOPLIN_BASE_URL", "http://joplin:22300")
            .with_env_variable("JOPLIN_ADMIN_EMAIL", "admin@localhost")
            .with_env_variable("JOPLIN_ADMIN_PASSWORD", "admin")
            .with_env_variable("FIXTURES_ROOT", "/workspace/fixtures")
            .with_exec(["pytest", "tests/seed", "-q", "--color=yes"])
            .stdout()
        )

        return joplin_service

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