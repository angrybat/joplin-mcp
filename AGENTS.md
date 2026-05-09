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

- `dagger call fixture-data --source=. --update-lock`
- `dagger call integration-tests --joplin-version=3.x.x --postgres-version=16`
- `dagger call publish-image --joplin-version=3.x.x --postgres-version=16`

## Key Paths
- Wrapper runtime: [src/joplin_mcp_wrapper/main.py](src/joplin_mcp_wrapper/main.py)
- Health probes: [src/joplin_mcp_wrapper/health.py](src/joplin_mcp_wrapper/health.py)
- Dagger pipeline entrypoint: [dagger/src/joplin_mcp/__init__.py](dagger/src/joplin_mcp/__init__.py)
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

## Stage Implementation Pattern

All Dagger stages must follow this standardized pattern to maintain module boundaries, avoid host filesystem APIs, and ensure consistent architecture across the pipeline.

### Required Pattern

1. **Source Directory Input** (when needed): If a stage requires access to repository files, accept exactly one `source: dagger.Directory` parameter representing the repository root. If the stage only runs external commands without reading repo files, the source parameter is optional.
   - When using source: derive all needed subdirectories from source (e.g., `source.directory("src")`)
   - Never use `dag.host()` or `dag.current_module().source()` to access host paths
   - Never traverse parent paths (e.g., `.directory("..")`)

2. **Orchestration in Module**: Stage function in [dagger/src/joplin_mcp/__init__.py](dagger/src/joplin_mcp/__init__.py) handles only:
   - Accepting source directory input (if needed)
   - Creating container
   - Optionally mounting source if stage uses it
   - Executing stage logic or script
   - Returning output directory from container

3. **Business Logic in Scripts** (when source is used): If a stage reads repository files, all file-accessing logic should live in a standalone script under [src/scripts](src/scripts):
   - Script accepts mounted paths as command-line arguments
   - Script performs all validation, generation, and error handling
   - Script writes outputs to an output directory (typically `/tmp/<stage>-out` in container)
   - Script works independently of the Dagger module context

4. **Container Execution**: Stage function builds a container that:
   - Optionally mounts source directory at `/workspace` (if needed)
   - Runs script or command with appropriate arguments
   - Returns directory from container at a predictable output path

### Implementation Checklist

Before marking a stage as in-progress, confirm:

- [ ] If stage reads repository files: function signature accepts one `source: dagger.Directory` parameter
- [ ] If stage doesn't read repository files: no source parameter needed; document why in stage docstring
- [ ] No `dag.host()` calls in the function
- [ ] No `source.directory("..")` or similar parent traversal (when source is used)
- [ ] If source is used: all business logic is in `src/scripts/<stage>.py` (or similar)
- [ ] Stage returns `dagger.Directory` from container output path
- [ ] If using script: script can run standalone with path arguments: `python <script> --input-root /path --output-root /path`
- [ ] If business logic in Dagger function: document justification in function docstring

### Example

See [fixture-data stage](dagger/src/joplin_mcp/__init__.py#L13-L41) and [generate_fixture_data.py](src/scripts/generate_fixture_data.py) as the reference implementation.

When implementing a new stage, start from the scaffold template at [.github/templates/STAGE_SCAFFOLD.py](.github/templates/STAGE_SCAFFOLD.py) — customize it and you'll naturally follow the pattern.

### Non-Compliance

If a stage cannot follow this pattern, the decision to deviate **must** be recorded in [PLAN.md](PLAN.md) Decision Log with explicit rationale and approval.

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
