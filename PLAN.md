---
plan_id: joplin-mcp-release-pipeline
status: not-started
last_updated: 2026-04-18
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
current_phase: documentation-bootstrap
next_action: scaffold project structure and initialize Python project
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
| **Fixture lock** | Checksum manifest that detects unexpected changes to expected test data |
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
- Integration tests are a **mandatory blocking gate** for image release.
- Supply chain checks are a **mandatory blocking gate** for image release.
- Chart release is **independent** of image release cadence.
- Joplin and Postgres versions are **explicit pipeline inputs**, never implicit.
- Fixture lock divergence **always fails** unless `--update-lock` mode is explicitly set.
- Delete operations on Joplin data are **disabled by default** in all policy configurations.

---

## Stage Catalog

### Stage: `fixture-data`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Generate the single source of truth for all integration test data. Produces both the Postgres seed inputs and the expected MCP response files used for assertions.

**Inputs:**
- Fixture definition files in `fixtures/definitions/`

**Outputs:**
- `fixtures/seed/` — SQL or structured data files for Postgres population
- `fixtures/expected/` — Expected MCP tool response files
- `fixtures/fixture.lock` — Checksum manifest over all expected outputs
- `fixtures/fixture-diff.md` — Human-readable diff report (produced on regeneration)

**Depends on:** none

**Success Criteria:**
- All fixture files are generated deterministically (identical output on repeated runs with same inputs).
- Fixture lock file matches generated checksums.
- No non-canonical values (e.g. unstable timestamps, random IDs) appear in outputs.

**Failure Criteria:**
- Non-deterministic output detected between runs.
- Fixture lock mismatch without `--update-lock` flag.

---

### Stage: `build-mcp-image`

**Status:** ⬜ Not started
**Started:** —
**Completed:** —

**Purpose:** Build the Joplin MCP wrapper Docker image from pinned dependencies.

**Inputs:**
- `src/joplin_mcp_wrapper/` — wrapper source code
- `pyproject.toml` — pinned `joplin-mcp` version
- Pinned Python base image reference
- `--platforms` pipeline argument (default: `linux/amd64,linux/arm64`)

**Outputs:**
- OCI image artifact
- Image digest
- OCI labels: `org.opencontainers.image.source`, `org.opencontainers.image.revision`, `org.opencontainers.image.version`

**Depends on:** none

**Success Criteria:**
- Image builds successfully from pinned dependencies.
- Wrapper process starts and health endpoints respond on expected port.
- Image digest is deterministic for identical inputs.

**Failure Criteria:**
- Build fails due to dependency resolution errors.
- Health endpoint does not respond after startup.

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
- `fixtures/fixture.lock` for checksum validation

**Outputs:**
- Test result report
- Pass/fail exit code

**Depends on:** `mcp-service`, `build-integration-runner-image`, `fixture-data`

**Blocking gate for:** `publish-image`

**Test Coverage:**
- Tool discovery returns expected tools.
- Read tool responses match `fixtures/expected/` contents.
- Response checksums match `fixtures/fixture.lock`.
- Allowed write operations succeed under correct policy flags.
- Denied operations return explicit policy-denied messages.
- Health probes: `/startupz`, `/livez`, `/readyz` behave correctly.

**Success Criteria:**
- All assertions pass.
- Fixture lock checksums match generated fixture outputs.

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
- Passing `integration-tests` result
- Passing `pre-publish-checks` result
- Git tag version (`vX.Y.Z`)

**Outputs:**
- Published multi-arch image at `docker.io/<org>/joplin-mcp:<version>` (linux/amd64 + linux/arm64)
- Published `latest` tag (stable releases only)
- Release metadata: version, digest, SBOM reference, provenance reference

**Depends on:** `integration-tests` (blocking), `pre-publish-checks` (blocking)

**Success Criteria:**
- Image published with correct semver tag.
- Release metadata emitted.

**Failure Criteria:**
- Either blocking gate has not passed.
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
fixture-data ─────────────────────────────────────────────────┐
                                                              ▼
build-fixture-tooling-image ──────────────────────────► postgres-service
                                                              │
                                                              ▼
                                                       joplin-service
                                                              │
build-mcp-image ──────────────────────────────────────► mcp-service
                │                                             │
                │                                             ▼
                │                         build-integration-runner-image
                │                                    │        │
                │                                    ▼        ▼
                │                           integration-tests ◄── fixture-data
                │                                    │
                ▼                                    │
        pre-publish-checks                           │
                │                                    │
                └──────────┬─────────────────────────┘
                           ▼
                     publish-image


chart/ ──► chart-change-detection ──► chart-lint ──► publish-chart
```

---

## Pipeline Modes

| Mode | Trigger | Stages Required |
|---|---|---|
| Image release | `vX.Y.Z` git tag | fixture-data, all builds, all services, integration-tests, pre-publish-checks, publish-image |
| Chart release | `chart-vX.Y.Z` git tag | chart-change-detection, chart-lint, publish-chart |
| Full release | both tags present | both paths |
| Integration test only | manual / PR | fixture-data, all builds, all services, integration-tests |

---

## Progress Ledger

_Append-only. Each entry records what changed, when, and why._

| Date | Change |
|---|---|
| 2026-04-18 | Plan created. Project status set to not-started. |

---

## Current State Snapshot

> **Rewrite this section** each time implementation state changes.

**As of 2026-04-18:**
- All stages: not started.
- Documentation baseline: in progress.
- Next action: scaffold project directory structure and initialize Python project.

---

## Decision Log

| Date | Decision | Rationale | Status |
|---|---|---|---|
| 2026-04-18 | Use upstream `alondmnt/joplin-mcp` via pip, not fork | Keeps upgrade path clean; wrapper handles Kubernetes concerns | Active |
| 2026-04-18 | Wrapper supervises joplin-mcp as child process | Allows independent health endpoints without modifying upstream | Active |
| 2026-04-18 | Streamable HTTP as primary transport | Required for hosted VS Code agent connectivity | Active |
| 2026-04-18 | Joplin + Postgres versions as explicit pipeline inputs | Ensures version matrix is always tested explicitly | Active |
| 2026-04-18 | Integration tests gate image publish only | Decouples chart cadence from image cadence | Active |
| 2026-04-18 | Chart release is change-driven and independent | Chart changes rarely; forcing re-release on every image bump adds no value | Active |
| 2026-04-18 | Fixture lock prevents silent expectation drift | Integration tests are only trustworthy if expected outputs are reviewed on change | Active |
| 2026-04-18 | Delete operations disabled by default via policy flags | Safety-first; additive writes only until explicitly relaxed | Active |
| 2026-04-18 | pre-publish-checks stage before publish-image | Supply chain integrity enforced before every public release | Active |
| 2026-04-18 | Combined publish-all stage removed | Partial release risk outweighed benefits; image and chart publish independently | Active |
| 2026-04-18 | Multi-arch image from the start | publish-image produces linux/amd64 + linux/arm64; build-mcp-image accepts `--platforms` argument | Active |
| 2026-04-18 | No API-level Joplin seeding | Postgres seeding is the only supported seeding path; no API-level fallback | Active |

---

## Open Questions

None.

---

## Agent Execution Notes

- **Always read the front matter** at the top of this file to get current phase and next action.
- **Run stages in dependency order.** Do not start a stage until its dependencies are complete.
- **Do not skip blocking gates.** `integration-tests` and `pre-publish-checks` must both pass before `publish-image` runs.
- **If fixture lock diverges**, fail and report — do not auto-update unless `--update-lock` is explicitly passed.
- **After completing a stage**, update its status, record the completion date, and add a ledger entry.
- **After completing any work session**, rewrite the Current State Snapshot to reflect actual state.
- **Do not implement anything outside the Included scope** without adding a decision log entry first.
