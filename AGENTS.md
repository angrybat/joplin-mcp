# AGENTS.md

## Purpose
This repository builds and publishes a hosted Joplin MCP server using a Python wrapper + Dagger pipeline.

## Start Here
- Read [README.md](README.md) for current project status and high-level architecture.
- Read [PLAN.md](PLAN.md) before implementing code. It is the stage contract and gate source of truth.

## Non-Negotiable Rules
- Use Dagger for build/test/publish workflows.
- Do not add or rely on a Dockerfile for image builds.
- Do not skip publish gates: `integration-tests` and `pre-publish-checks` must pass before `publish-image`.
- Treat fixture lock as authoritative: do not hand-edit [fixtures/fixture.lock](fixtures/fixture.lock).
- Postgres seeding is the only seeding path; do not implement API-level fallback seeding.

## Build/Test Commands
Run from repository root:

- `dagger call fixture-data --update-lock`
- `dagger call integration-tests --joplin-version=3.x.x --postgres-version=16`
- `dagger call publish-image --joplin-version=3.x.x --postgres-version=16`

## Key Paths
- Wrapper runtime: [src/joplin_mcp_wrapper/main.py](src/joplin_mcp_wrapper/main.py)
- Health probes: [src/joplin_mcp_wrapper/health.py](src/joplin_mcp_wrapper/health.py)
- Dagger pipeline entrypoint: [dagger/main.py](dagger/main.py)
- Integration fixture guard: [tests/integration/conftest.py](tests/integration/conftest.py)
- Helm chart: [chart/Chart.yaml](chart/Chart.yaml), [chart/values.yaml](chart/values.yaml)
- Repository license: [LICENSE](LICENSE)

## Environment Expectations
Wrapper/runtime variables used by the code:
- `JOPLIN_HOST` (required)
- `JOPLIN_TOKEN` (required)
- `MCP_PORT` (default `8000`)
- `HEALTH_PORT` (default `8001`)
- `READYZ_CACHE_SECONDS` (default `10`)
- `READYZ_TIMEOUT_SECONDS` (default `2.0`)

## Working Conventions for Agents
- Commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) (`<type>[scope]: <description>`). Common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`.
- Keep changes stage-scoped and aligned to [PLAN.md](PLAN.md) dependency order.
- When implementation status changes, update status sections in [README.md](README.md) and stage/snapshot fields in [PLAN.md](PLAN.md).
- Prefer minimal, deterministic changes; avoid incidental refactors.
- If a task changes architecture or release behavior, add a Decision Log entry in [PLAN.md](PLAN.md).
- Treat the root [LICENSE](LICENSE) file as the canonical source of repository licensing terms.
- Keep [LICENSE](LICENSE), [pyproject.toml](pyproject.toml), and license references in README files in sync when licensing or distribution metadata changes.

## Agent Skills
- The skill catalog lives in [SKILLS.md](SKILLS.md); slash-discoverable skill implementations live under `.github/skills/`.
- Use **Plan Progress Sync** after meaningful work sessions to reconcile conversation progress with [PLAN.md](PLAN.md) and synchronize [README.md](README.md).
- If implementation diverges from the written plan but remains valid, update documentation to reflect reality and record rationale as required by [PLAN.md](PLAN.md).
- Expand companion documentation when conversation evidence reveals missing guidance or outdated contracts.
