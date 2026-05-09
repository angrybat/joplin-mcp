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
    async def unit_tests(self, source: dagger.Directory) -> str:
        return await (
            self._python_container(source)
            .with_exec(
                [
                    "python",
                    "-m",
                    "pip",
                    "install",
                    "--root-user-action=ignore",
                    ".[unit-tests]",
                ]
            )
            .with_exec(
                [
                    "python",
                    "-m",
                    "pytest",
                    "tests/unit/test_main.py",
                    "-q",
                    "-ra",
                    "-W",
                    "default",
                ]
            )
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