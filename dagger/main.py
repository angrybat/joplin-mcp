"""
Dagger pipeline for joplin-mcp.

Stages (see PLAN.md for full stage contracts):
  fixture_data                 — generate fixture data and lock
  build_mcp_image              — build the MCP wrapper Docker image
  build_integration_runner     — build the integration test runner image
  build_fixture_tooling        — build the fixture generation tooling image
  postgres_service             — start seeded Postgres service
  joplin_service               — start Joplin service against seeded Postgres
  mcp_service                  — start MCP wrapper service against Joplin
  integration_tests            — run integration test suite
  pre_publish_checks           — SBOM, vulnerability scan, image signing
  publish_image                — publish Docker image to Docker Hub
  publish_chart                — publish Helm chart to Docker Hub OCI

All stages are invoked via `dagger call <stage-name> [args]`.
"""

import dagger
from dagger import dag, function, object_type


@object_type
class JoplinMcp:

    @function
    async def build_mcp_image(self) -> dagger.Container:
        """
        Stage: build-mcp-image
        Build the Joplin MCP wrapper image from pinned dependencies.
        Status: not-started — stub only.
        """
        raise NotImplementedError("build_mcp_image not yet implemented — see PLAN.md Phase 2")

    @function
    async def fixture_data(self, update_lock: bool = False) -> dagger.Directory:
        """
        Stage: fixture-data
        Generate deterministic fixture data for seeding and integration assertions.
        Status: not-started — stub only.

        Args:
            update_lock: When True, regenerate fixture.lock and emit fixture-diff report.
        """
        raise NotImplementedError("fixture_data not yet implemented — see PLAN.md Phase 1")

    @function
    async def postgres_service(
        self,
        postgres_version: str,
    ) -> dagger.Service:
        """
        Stage: postgres-service
        Start seeded Postgres service for the given version.
        Status: not-started — stub only.
        """
        raise NotImplementedError("postgres_service not yet implemented — see PLAN.md Phase 3")

    @function
    async def joplin_service(
        self,
        joplin_version: str,
        postgres_version: str,
    ) -> dagger.Service:
        """
        Stage: joplin-service
        Start Joplin service connected to seeded Postgres.
        Status: not-started — stub only.
        """
        raise NotImplementedError("joplin_service not yet implemented — see PLAN.md Phase 4")

    @function
    async def mcp_service(
        self,
        joplin_version: str,
        postgres_version: str,
    ) -> dagger.Service:
        """
        Stage: mcp-service
        Start MCP wrapper service connected to Joplin.
        Status: not-started — stub only.
        """
        raise NotImplementedError("mcp_service not yet implemented — see PLAN.md Phase 5")

    @function
    async def integration_tests(
        self,
        joplin_version: str,
        postgres_version: str,
    ) -> str:
        """
        Stage: integration-tests  [BLOCKING GATE for publish-image]
        Run the full integration test suite.
        Status: not-started — stub only.
        """
        raise NotImplementedError("integration_tests not yet implemented — see PLAN.md Phase 6")

    @function
    async def pre_publish_checks(self) -> str:
        """
        Stage: pre-publish-checks  [BLOCKING GATE for publish-image]
        Run SBOM generation, vulnerability scan, and image signing.
        Status: not-started — stub only.
        """
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
        """
        Stage: publish-image
        Publish Docker image to Docker Hub. Requires integration-tests and
        pre-publish-checks to pass first.
        Status: not-started — stub only.
        """
        raise NotImplementedError("publish_image not yet implemented — see PLAN.md Phase 8")

    @function
    async def publish_chart(
        self,
        version: str,
        registry_username: dagger.Secret,
        registry_password: dagger.Secret,
    ) -> str:
        """
        Stage: publish-chart
        Publish Helm chart to Docker Hub OCI. Only runs when chart content has changed.
        Status: not-started — stub only.
        """
        raise NotImplementedError("publish_chart not yet implemented — see PLAN.md Phase 9")
