---
plan_id: joplin-mcp-release-pipeline
status: in-progress
last_updated: 2026-05-09
primary_audience:
  - humans
  - vscode_agents
source_of_truth: git_tags_semver
version_inputs:
  joplin: required           # passed as --joplin-version pipeline argument
  postgres: required         # passed as --postgres-version pipeline argument
release_modes:
  - image                    # triggered by vX.Y.Z git tag
  - chart                    # triggered by chart-vX.Y.Z git tag
current_phase: build-mcp-image-in-progress
next_action: Complete build-mcp-image metadata/determinism validation and sync status evidence in README/PLAN.
---

# Joplin MCP — Execution Plan

<!--
  AI AGENT INSTRUCTIONS
  ---------------------
  This file is the authoritative source for implementation decisions, stage
  contracts, and project status. Read this before writing any code.

  Rules for agents:
  1. Do not implement a stage whose status is "blocked" without resolving the
     listed blocker first.
  2. When you start work on a stage, update its status to "in-progress" and
     record the date.
  3. When a stage is complete, update its status to "complete", record the date,
     and add evidence (file paths, test output, or PR reference).
  4. Every architectural change must add a new entry to the Decision Log.
  5. Do not alter the fixture.lock file directly; only fixture-data stage tooling
     may regenerate it.
  6. Never skip a blocking gate to publish an image or chart.
  7. Keep next_action in the YAML front matter up to date.
-->

## Definitions

| Term | Meaning |
|---|---|
| **Dagger stage** | An isolated unit of pipeline work implemented as a Dagger function |
| **Fixture** | Deterministic mock data used for both Postgres seeding and integration assertions |
| **Fixture lock** | Committed checksum manifest for generated fixture artifacts used as a reviewed baseline |
| **Fixture drift** | When expected outputs change silently without explicit review |
| **Policy flag** | Environment variable that enables or disables a Joplin write capability |
| **Blocking gate** | A stage that must pass before a publish stage may proceed |
| **MCP wrapper** | Thin Python process that supervises `joplin-mcp` subprocess and serves health endpoints |
| **Version inputs** | `--joplin-version` and `--postgres-version` pipeline arguments; required for all service stages |

---

## Project Overview

This project wraps the upstream [`alondmnt/joplin-mcp`](https://github.com/alondmnt/joplin-mcp)
Python package into a production-grade hosted MCP server. The server runs on Kubernetes,
exposes Streamable HTTP MCP transport, and provides standard Kubernetes health probes.

**Primary outcomes:**
- Publish a versioned Docker image to Docker Hub.
- Publish a versioned Helm chart to Docker Hub OCI registry.
- Validate MCP compatibility against explicit Joplin and Postgres version inputs.
- Keep integration tests trustworthy through fixture locking and drift prevention.
- Enforce supply-chain checks before every image release.

---

## Scope

### Included
- Python wrapper application (built into a container image inside the Dagger pipeline — no standalone Dockerfile).
- Dagger pipeline with all stages defined below.
- Helm chart for Kubernetes deployment.
- VS Code MCP client configuration.
- Integration test suite backed by fixture data.
- Supply chain checks (SBOM, vulnerability scan, image signing).

### Excluded
- Kubernetes cluster provisioning (lives in homeservers repo).
- Istio Gateway and VirtualService manifests (lives in homeservers repo).
- Pi-hole DNS configuration (lives in homeservers repo).
- Mobile access layer (deferred).

---

## Global Constraints

- Build stages have **no service dependencies**; they run independently.
- Service stages compose in strict dependency order.
- The `tests` stage is the **mandatory test blocking gate** for image release.
- Unit tests should be implemented before the integration test suite, but they do not block `integration-tests` execution.
- A combined `tests` stage must run unit and integration suites concurrently and pass only when both pass.
- Supply chain checks are a **mandatory blocking gate** for image release.
- Chart release is **independent** of image release cadence.
- Joplin and Postgres versions are **explicit pipeline inputs**, never implicit.
- Canonical fixture definitions are Markdown files in notebook-like folder trees under `fixtures/definitions/`.
- Fixture lock divergence **always fails** unless `--update-lock` mode is explicitly set.
- Fixture lock checksum scope includes only generated artifacts in `fixtures/seed/**` and `fixtures/expected/**`.
- `fixtures/definitions/**` files are canonical inputs but are excluded from fixture lock hashing.
- Delete operations on Joplin data are **disabled by default** in all policy configurations.

---

## Stage Catalog

### Stage: `fixture-data`

**Status:** ✅ Complete
**Started:** 2026-04-28
**Completed:** 2026-05-09

**Purpose:** Generate the single source of truth for all integration test data. Produces both the Postgres seed inputs and the expected MCP response files used for assertions.

**Inputs:**
- Canonical Markdown fixture definitions in `fixtures/definitions/` (folder hierarchy maps to notebooks)
- Deterministic fixture metadata from Markdown frontmatter (stable IDs, tags, policy flags)

**Outputs:**
- `fixtures/seed/` — Deterministic SQL seed files for Postgres population
- `fixtures/expected/` — Expected MCP tool response files
- `fixtures/fixture.lock` — Committed checksum manifest over generated fixture outputs (`seed/` + `expected/`) (written only in `--update-lock` mode)
- `fixtures/fixture-diff.md` — Human-readable diff report (written only in `--update-lock` mode)

**Depends on:** none

**Success Criteria:**
- All fixture files are generated deterministically (identical output on repeated runs with same inputs).
- Default mode (`dagger call fixture-data --source=.`) generates `seed/` and `expected/` without modifying `fixture.lock`.
- Update mode (`dagger call fixture-data --source=. --update-lock`) regenerates `fixture.lock` and `fixture-diff.md` from generated outputs.
- Fixture lock file matches generated checksums for `seed/` and `expected/` and is committed when fixture output changes are intentional.
- No non-canonical values (e.g. unstable timestamps, random IDs) appear in outputs.

**Failure Criteria:**
- Non-deterministic output detected between runs.
- Lock file is missing in default mode (must instruct operator to run `dagger call fixture-data --source=. --update-lock`).
- Fixture lock mismatch without `--update-lock` flag.

**Execution Modes:**
- **Default mode:** `dagger call fixture-data --source=.`
  - Generates `fixtures/seed/` and `fixtures/expected/`.
  - Compares checksums for generated outputs against `fixtures/fixture.lock`.
  - Does not create or modify lock files.
- **Update mode:** `dagger call fixture-data --source=. --update-lock`
  - Generates `fixtures/seed/` and `fixtures/expected/`.
  - Regenerates `fixtures/fixture.lock` from generated output checksums.
  - Regenerates `fixtures/fixture-diff.md` for review.

---

### Stage: `build-mcp-image`

**Status:** 🟡 In progress
**Started:** 2026-05-09
**Completed:** —

**Purpose:** Build the Joplin MCP wrapper Docker image from pinned dependencies.

**Inputs:**
- `--source` pipeline argument (repository root directory)
- `src/joplin_mcp_wrapper/` — wrapper source code
- `pyproject.toml` — pinned `joplin-mcp` version
- Pinned Python base image reference

**Function Contract:**
- `build-mcp-image(source) -> dagger.Container`

**Outputs:**
- OCI image artifact
- Image digest
- Runtime-ready MCP wrapper entrypoint image (OCI labels are applied in `publish-image` stage)

**Depends on:** none

**Success Criteria:**
- Image builds successfully from pinned dependencies.
- Wrapper process starts and health endpoints respond on expected port.
- Image digest is deterministic for identical inputs.

**Failure Criteria:**
- Build fails due to dependency resolution errors.
- Health endpoint does not respond after startup.

---

### Stage: `unit-tests`

**Status:** ✅ Complete
**Started:** 2026-05-09
**Completed:** 2026-05-09

**Purpose:** Run fast, deterministic unit tests for the wrapper code.

**Inputs:**
- `src/joplin_mcp_wrapper/` — wrapper source code
- `tests/unit/` — unit test suite
- Python test dependencies from `pyproject.toml`

**Outputs:**
- Test result report
- Pass/fail exit code

**Depends on:** none

**Blocking gate for:** `tests`

**Test Coverage:**
- Environment validation rejects missing required configuration.
- Child command construction uses expected MCP transport and port.
- Supervisor loop updates child process state across startup and restart paths.
- Health probes return the expected startup, liveness, and readiness responses.
- Readiness caching avoids repeated Joplin reachability checks inside the cache window.

**Success Criteria:**
- All assertions pass.
- Tests run without requiring live Joplin or Postgres services.

**Failure Criteria:**
- Any assertion fails.
- Test execution depends on external services or non-deterministic timing.

---

### Stage: `build-integration-runner-image`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Build the image used to execute integration tests.

**Inputs:**
- `tests/integration/` — test suite
- Test dependency definitions

**Outputs:**
- OCI image artifact with test tooling installed
- Supports fixture directory bind mount at `/fixtures`

**Depends on:** none

**Success Criteria:**
- Image builds successfully.
- Test runner executes without errors against a mock target.

**Failure Criteria:**
- Build fails or test runner cannot be invoked.

---

### Stage: `build-fixture-tooling-image`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Build the image that generates and validates fixture data.

**Inputs:**
- Fixture tooling source in `dagger/fixtures/`

**Outputs:**
- OCI image artifact for fixture generation and lock validation

**Depends on:** none

**Success Criteria:**
- Image builds and fixture generation produces expected directory structure.

**Failure Criteria:**
- Build fails or fixture tooling does not produce consistent outputs.

---

### Stage: `postgres-service`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Start a Postgres service container and seed it with fixture data.

**Inputs:**
- `--postgres-version` pipeline argument
- `fixtures/seed/` directory from `fixture-data` stage

**Outputs:**
- Running Postgres service endpoint for downstream stages

**Depends on:** `fixture-data`

**Success Criteria:**
- Postgres starts on selected version.
- All seed inputs are applied without errors.
- Schema and row counts match expected values.

**Failure Criteria:**
- Postgres fails to start.
- Seed application fails or produces unexpected schema.

---

### Stage: `joplin-service`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Start a Joplin Server service container connected to seeded Postgres.

**Inputs:**
- `--joplin-version` pipeline argument
- Running Postgres service from `postgres-service` stage

**Outputs:**
- Running Joplin service endpoint and API token for downstream stages

**Depends on:** `postgres-service`

**Success Criteria:**
- Joplin starts on selected version and completes schema creation or upgrade.
- Joplin Data API responds to baseline read requests.
- Seeded data is accessible through Joplin API.

**Failure Criteria:**
- Joplin fails to start or schema upgrade fails.
- Baseline API calls return unexpected responses.
- Schema version mismatch with explicit diagnostic output.

---

### Stage: `mcp-service`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Start the Joplin MCP wrapper as a service connected to Joplin.

**Inputs:**
- Built MCP image from `build-mcp-image`
- Running Joplin service from `joplin-service`
- Joplin API token

**Outputs:**
- Running MCP service endpoint for integration tests

**Depends on:** `build-mcp-image`, `joplin-service`

**Success Criteria:**
- MCP wrapper starts and child `joplin-mcp` process binds successfully.
- `/startupz` returns 200 after startup completes.
- MCP tool discovery returns expected tool list.

**Failure Criteria:**
- Child process fails to start or bind.
- Tool discovery returns empty or error response.

---

### Stage: `integration-tests`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Run the full integration test suite against the live MCP service with fixture data.

**Inputs:**
- Running MCP service from `mcp-service`
- `fixtures/` directory mounted read-only at `/fixtures`
- `fixtures/fixture.lock` committed baseline for checksum validation of generated outputs

**Outputs:**
- Test result report
- Pass/fail exit code

**Depends on:** `mcp-service`, `build-integration-runner-image`, `fixture-data`

**Blocking gate for:** `tests`

**Test Coverage:**
- Tool discovery returns expected tools.
- Read tool responses match `fixtures/expected/` contents.
- Checksums for generated outputs in `fixtures/expected/` and `fixtures/seed/` match the committed `fixtures/fixture.lock` baseline.
- Allowed write operations succeed under correct policy flags.
- Denied operations return explicit policy-denied messages.
- Health probes: `/startupz`, `/livez`, `/readyz` behave correctly.

**Success Criteria:**
- All assertions pass.
- Fixture lock checksums match generated fixture outputs.
---

### Stage: `tests`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Run the unit and integration suites concurrently as the unified test gateway for PR validation and image release preparation.

**Inputs:**
- `unit-tests` stage definition and prerequisites
- `integration-tests` stage definition and prerequisites

**Outputs:**
- Combined test execution summary
- Pass/fail exit code covering both suites

**Depends on:** `unit-tests`, `integration-tests`

**Blocking gate for:** `publish-image`

**Success Criteria:**
- Both `unit-tests` and `integration-tests` pass.
- The stage emits clear output identifying which suite failed when there is a failure.

**Failure Criteria:**
- Either test suite fails.
- The stage serializes the two suites instead of allowing Dagger to execute them concurrently.

**Execution Notes:**
- This stage runs `unit-tests` and `integration-tests` together and succeeds only if both suites pass.
- Each suite remains independently invokable outside this stage.

**Failure Criteria:**
- Any assertion fails.
- Fixture lock divergence detected (unless `--update-lock` is set).
- Transport error or service unreachable.

---

### Stage: `pre-publish-checks`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Enforce supply-chain quality gates before image publishing.

**Inputs:**
- Built MCP image from `build-mcp-image`

**Outputs:**
- SBOM artifact (SPDX or CycloneDX format)
- Vulnerability scan report
- Image signature and provenance attestation

**Depends on:** `build-mcp-image`

**Blocking gate for:** `publish-image`

**Success Criteria:**
- SBOM generated successfully.
- No vulnerabilities above configured severity threshold (default: block on Critical and High).
- Image signed and provenance attestation produced.

**Failure Criteria:**
- Vulnerability scan exceeds threshold.
- Signing fails.

---

### Stage: `publish-image`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Publish the MCP wrapper Docker image to Docker Hub.

**Inputs:**
- Built MCP image from `build-mcp-image`
- Passing `tests` result
- Passing `pre-publish-checks` result
- Git tag version (`vX.Y.Z`)

**Outputs:**
- Published multi-arch image at `docker.io/<org>/joplin-mcp:<version>` (linux/amd64 + linux/arm64)
- Published `latest` tag (stable releases only)
- Release metadata: version, digest, SBOM reference, provenance reference

**Depends on:** `tests` (blocking), `pre-publish-checks` (blocking)

**Success Criteria:**
- Image published with correct semver tag.
- Release metadata emitted.

**Failure Criteria:**
- Any blocking gate has not passed.
- Docker Hub push fails.

---

### Stage: `publish-chart`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Publish the Helm chart to Docker Hub OCI registry.

**Inputs:**
- `chart/` directory
- Chart change detection result (only runs when chart content changed)
- Git tag version (`chart-vX.Y.Z`)

**Outputs:**
- Published Helm chart at `oci://registry-1.docker.io/<org>/joplin-mcp-chart:<version>`

**Depends on:** chart-change detection, chart lint and template validation

**Success Criteria:**
- Chart lint and template validation pass.
- Chart published with correct semver.
- Chart `values.yaml` exposes `image.repository` and `image.tag` fields.

**Failure Criteria:**
- Chart lint fails.
- No chart changes detected (stage skipped, not failed).
- Push fails.

---

## Stage Dependency Graph

```
INDEPENDENT STAGES (Layer 0)
├── fixture-data
├── build-mcp-image
├── build-fixture-tooling-image
├── build-integration-runner-image
└── unit-tests (src/ + tests/unit)


LEVEL 1: DIRECT DEPENDENCIES
├── postgres-service         ◄─── fixture-data
└── pre-publish-checks       ◄─── build-mcp-image


LEVEL 2: POSTGRES DEPENDENT
└── joplin-service           ◄─── postgres-service


LEVEL 3: JOPLIN + BUILD DEPENDENT
└── mcp-service              ◄─── build-mcp-image
                                  joplin-service


LEVEL 4: SERVICE + BUILD + FIXTURE DEPENDENT
└── integration-tests        ◄─── mcp-service
                                  build-integration-runner-image
                                  fixture-data


LEVEL 5: BOTH TEST SUITES
└── tests                    ◄─── unit-tests
                                  integration-tests


LEVEL 6: PUBLISH TEST GATE + SUPPLY CHAIN
└── publish-image           ◄─── tests
                                  pre-publish-checks


INDEPENDENT: CHART RELEASE FLOW
chart/ ──► chart-change-detection ──► chart-lint ──► publish-chart
```

---

## Pipeline Modes

| Mode | Trigger | Stages Required |
|---|---|---|
| Image release | `vX.Y.Z` git tag | fixture-data, all builds, unit-tests, all services, integration-tests, tests, pre-publish-checks, publish-image |
| Chart release | `chart-vX.Y.Z` git tag | chart-change-detection, chart-lint, publish-chart |
| Full release | both tags present | both paths |
| Unit test only | manual / PR | unit-tests |
| Integration test only | manual / PR | fixture-data, all builds, all services, integration-tests |
| Test gateway run | manual / PR | fixture-data, all builds, all services, tests |

---

## Progress Ledger

_Append-only. Each entry records what changed, when, and why._

| Date | Change |
|---|---|
| 2026-04-18 | Plan created. Project status set to not-started. |
| 2026-04-19 | Added dedicated `unit-tests` and `integration-tests` stages plus a `tests` gateway stage that passes only when both suites pass. |
| 2026-04-25 | Added canonical documentation sync skill in `SKILLS.md` and wired agent discovery in `AGENTS.md`; updated plan governance fields for ongoing work. |
| 2026-04-28 | Moved Plan Progress Sync into the VS Code skill directory at `.github/skills/plan-progress-sync/SKILL.md`, refreshed companion docs, and documented slash-command discovery. |
| 2026-04-28 | Completed fixture-data Phase 1 contract alignment: Markdown notebook-tree definitions, deterministic SQL seed output, committed lock baseline over generated outputs, and Pirate Fleet Logbook initial fixture theme with Captain Diary coverage. |
| 2026-04-28 | Completed fixture-data Phase 2 contract alignment: added explicit default/update execution modes, lock hash scope (`seed` + `expected` only), missing-lock failure behavior, and documented lock update/export commands. |
| 2026-04-28 | Started fixture-data Phase 3 implementation in `dagger/main.py`: default mode now generates deterministic `seed/` and `expected/` outputs and validates lock divergence against generated artifact checksums; update-lock mode remains pending. |
| 2026-04-30 | Refactored fixture-data Phase 3 implementation to run generation and lock validation inside a Python container via `dagger/src/joplin_mcp/__init__.py` and `src/scripts/generate_fixture_data.py`, consolidating fixture logic into a single script and using repo-root directory input (`--source`). End-to-end pass evidence is still pending because `dagger call fixture-data --source=.` currently exits non-zero. |
| 2026-05-09 | Implemented Dagger stage implementation guardrails: (1) documented Stage Implementation Pattern in AGENTS.md with flexible source directory requirement (required only when stages read repo files; optional for external-command-only stages); (2) created validation script `.github/scripts/validate-dagger-stage-pattern.py` to automatically detect forbidden patterns (`dag.host()`, parent traversal, `dag.current_module().source()`); (3) created stage scaffold template at `.github/templates/STAGE_SCAFFOLD.py` with both patterns (repo-file-reading and external-command-only); (4) added Decision Log entry documenting mandatory pattern with architectural rationale. Validation script tested and passes. |
| 2026-05-09 | Completed fixture-data Phase 1 implementation by authoring the full 13-note Pirate Fleet Logbook catalog under `fixtures/definitions/` and validating parser compatibility via `read_markdown_definitions` in `src/scripts/generate_fixture_data.py` (13 definitions loaded successfully). |
| 2026-05-09 | Completed fixture-data Phase 2 implementation by adding update-lock generation to `src/scripts/generate_fixture_data.py`, including committed lock rendering and human-readable diff output in fixture-data update mode. |
| 2026-05-09 | Completed fixture-data Phase 4 (guardrails & handoff): fixed integration fixture guard scope in `tests/integration/conftest.py` to validate generated outputs (`seed/` + `expected/`) against committed lock checksums (not definitions); conftest guard validation passed with no lock divergence detected; updated PLAN.md and README.md with completion evidence; fixture-data stage is now complete and unblocks parallel execution of build-mcp-image and unit-tests. |
| 2026-05-09 | Completed unit-tests Phase 2: added `unit_tests(source)` Dagger function in `dagger/src/joplin_mcp/__init__.py` that runs `tests/unit/test_main.py` in a Python 3.12 container after installing test dependencies including `pytest-asyncio`; fixed async return handling by awaiting `.stdout()`; validation evidence: `dagger call unit-tests --source=.` completed successfully with `1 passed` and no `asyncio_mode` warning in containerized output. |
| 2026-05-09 | Completed unit-tests Phase 3: implemented remaining wrapper unit-test coverage with new `src/joplin_mcp_wrapper/health.py` readiness/cache helpers and expanded `src/joplin_mcp_wrapper/main.py` command + supervisor state primitives; added `tests/unit/test_health.py` and expanded `tests/unit/test_main.py`; broadened Dagger unit test execution to `tests/unit`; validation evidence: local `pytest tests/unit -q` => `6 passed` and `dagger call unit-tests --source .` => `6 passed`. |
| 2026-05-09 | Refined unit-tests for clearer state isolation: split combined assertions into focused per-state tests in `tests/unit/test_main.py` and `tests/unit/test_health.py`; validation evidence: `dagger call unit-tests --source .` => `15 passed` across full `tests/unit` suite. |

---

## Current State Snapshot

> **Rewrite this section** each time implementation state changes.

**As of 2026-05-09:**
- `fixture-data`: ✅ complete (end-to-end containerized generation with default and update-lock modes fully implemented; all 13 canonical Pirate Fleet Logbook fixture definitions authored and committed under `fixtures/definitions/`; deterministic SQL seed and expected MCP outputs generated and committed; fixture.lock baseline committed with SHA256 checksums for `fixtures/seed/seed.sql` and `fixtures/expected/notes.json`; integration fixture guard fixed and validated against committed lock with no divergence; ready to unblock parallel phases build-mcp-image and unit-tests).
- `unit-tests`: ✅ complete (Phase 1 env validation baseline plus Phase 3 coverage for command construction, supervisor state transitions, health responses, and readiness caching; suite refined into focused state tests; validation: `dagger call unit-tests --source .` passes with 15 tests).
- Remaining stages: not started.
- Documentation baseline: fixture-data Phases 1-2 contract alignment complete; Phase 3 architecture refactored to containerized script execution.
- Guardrails system: Stage Implementation Pattern documented in AGENTS.md; validation script implemented and passing; scaffold template created for future stages.
- Repository licensing: MPL-2.0 documented via root LICENSE and package/docs references.
- Next action: begin `build-mcp-image` stage implementation and validate wrapper startup and health endpoint behavior in-container.

---

## Decision Log

| Date | Decision | Rationale | Status |
|---|---|---|---|
| 2026-04-18 | Use upstream `alondmnt/joplin-mcp` via pip, not fork | Keeps upgrade path clean; wrapper handles Kubernetes concerns | Active |
| 2026-04-18 | Wrapper supervises joplin-mcp as child process | Allows independent health endpoints without modifying upstream | Active |
| 2026-04-18 | Streamable HTTP as primary transport | Required for hosted VS Code agent connectivity | Active |
| 2026-04-18 | Joplin + Postgres versions as explicit pipeline inputs | Ensures version matrix is always tested explicitly | Active |
| 2026-04-18 | Automated tests gate image publish only | Decouples chart cadence from image cadence while keeping chart release independent | Superseded |
| 2026-04-18 | Chart release is change-driven and independent | Chart changes rarely; forcing re-release on every image bump adds no value | Active |
| 2026-04-18 | Fixture lock prevents silent expectation drift | Integration tests are only trustworthy if expected outputs are reviewed on change | Active |
| 2026-04-18 | Delete operations disabled by default via policy flags | Safety-first; additive writes only until explicitly relaxed | Active |
| 2026-04-18 | pre-publish-checks stage before publish-image | Supply chain integrity enforced before every public release | Active |
| 2026-04-18 | Combined publish-all stage removed | Partial release risk outweighed benefits; image and chart publish independently | Active |
| 2026-04-18 | Multi-arch image from the start | publish-image produces linux/amd64 + linux/arm64; build-mcp-image accepts `--platforms` argument | Active |
| 2026-04-18 | No API-level Joplin seeding | Postgres seeding is the only supported seeding path; no API-level fallback | Active |
| 2026-04-19 | Repository licensed under MPL-2.0 via root LICENSE file | Keeps licensing terms canonical in one file while package and docs point to the same source | Active |
| 2026-04-19 | Conventional Commits adopted as commit message standard | Consistent history format enables changelog generation and clear intent signalling for agents and humans alike | Active |
| 2026-04-19 | Add `unit-tests` as an independently runnable test stage | Fast wrapper validation should exist separately from live-service testing and be implementable first | Active |
| 2026-04-19 | Add `tests` as the publish test gateway | Image publishing should depend on one test gate that represents both unit and integration suites passing together | Active |
| 2026-04-25 | Add Plan Progress Sync documentation skill | Keeps PLAN/README/AGENTS aligned with actual conversation progress, including divergence handling and doc expansion when gaps are found | Active |
| 2026-04-28 | Canonical fixture definitions use Markdown notebook trees with frontmatter metadata | Keeps fixture authoring human-friendly while preserving deterministic transforms into seed and expected outputs | Active |
| 2026-04-28 | `fixtures/fixture.lock` remains committed and validates generated fixture outputs | Provides a reviewed baseline to catch behavior drift beyond same-run consistency checks | Active |
| 2026-04-28 | Initial fixture content theme is Pirate Fleet Logbook with Captain Diary notes | Makes fixture diffs more recognizable and ensures coverage of both operational and narrative Markdown content | Active |
| 2026-04-28 | fixture-data runs in default and update-lock modes | Separates artifact generation from lock regeneration so lock updates are explicit and reviewable | Active |
| 2026-04-28 | fixture.lock checksum scope is generated outputs only (`seed/**`, `expected/**`) | Prevents source definition hashing from conflicting with generated-output contract | Active |
| 2026-04-30 | fixture-data stage accepts one repo-root source directory and executes a single consolidated script inside a Python container | Keeps module boundaries scope-safe and centralizes generation plus lock logic in `src/scripts/generate_fixture_data.py` | Active |
| 2026-05-09 | All Dagger stages follow standardized pattern: (1) stages reading repo files accept single `source: dagger.Directory`; (2) orchestration only in module; (3) file-accessing logic in `src/scripts`; (4) no `dag.host()` or parent traversal. Stages executing only external commands (no repo file access) may omit source parameter. | Maintains module scope boundaries, ensures consistency, enables automated validation, prevents host filesystem API drift while allowing flexibility for stateless/external-only operations | Active |

---

## Open Questions

None.

---

## Fixture Lock Commands

- Drift check and generate artifacts (no lock writes): `dagger call fixture-data --source=.`
- Regenerate lock and diff artifacts: `dagger call fixture-data --source=. --update-lock`
- Export regenerated fixture artifacts to workspace for commit: `dagger call fixture-data --source=. --update-lock export --path=./fixtures`

---

## Agent Execution Notes

- **Always read the front matter** at the top of this file to get current phase and next action.
- **Run stages in dependency order.** Do not start a stage until its dependencies are complete.
- **Do not skip blocking gates.** `tests` and `pre-publish-checks` must both pass before `publish-image` runs.
- **Keep `unit-tests` and `integration-tests` independent.** The unit suite should be implemented first, but the integration stage must not depend on the unit stage to execute.
- **Use `tests` when both suites should run together.** This stage is the unified test gateway and must report failures clearly.
- **If fixture lock diverges**, fail and report — do not auto-update unless `--update-lock` is explicitly passed.
- **After completing a stage**, update its status, record the completion date, and add a ledger entry.
- **After completing any work session**, rewrite the Current State Snapshot to reflect actual state.
- **Do not implement anything outside the Included scope** without adding a decision log entry first.
- **Treat the root LICENSE as canonical** and keep packaging metadata and README/agent references aligned with it.
