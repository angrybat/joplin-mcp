# joplin-mcp

<!--
  AI AGENT INSTRUCTIONS
  ---------------------
  This file is the human-and-agent-facing overview of the project.
  - Read this file first to understand project intent, scope, and current status.
  - Do not implement anything that contradicts the decisions in PLAN.md.
  - When implementation state changes, update the "Current Status" and
    "Stage Progress" sections to reflect actual reality.
  - Never mark a stage complete without evidence (file paths, test output, etc.).
  - For detailed stage contracts, inputs/outputs, and gates, read PLAN.md.
-->

## Overview

`joplin-mcp` packages the [`alondmnt/joplin-mcp`](https://github.com/alondmnt/joplin-mcp)
Python package as a production-ready, hosted MCP server for use with VS Code agents and
other MCP-compatible clients.

The server exposes Joplin note-taking data through the Model Context Protocol (MCP) over
Streamable HTTP transport. It includes a minimal Python wrapper process that supervises the
upstream `joplin-mcp` subprocess and exposes Kubernetes-compatible health endpoints.

A Helm chart is provided to deploy the service to a Kubernetes cluster. The chart supports
configurable image repository and tag so image releases and chart releases are independent.

---

## Architecture

```
VS Code Agent
     │
     │  Streamable HTTP (MCP)
     ▼
┌─────────────────────────────┐
│  joplin-mcp wrapper         │
│  ┌───────────────────────┐  │
│  │  joplin-mcp subprocess│  │  ← upstream Python package (pinned version)
│  └───────────────────────┘  │
│  /startupz  /livez  /readyz │  ← Kubernetes health endpoints
└─────────────────────────────┘
     │
     │  Joplin Data API (port 22300)
     ▼
Joplin Server
     │
     ▼
PostgreSQL
```

**Key design choices:**
- Upstream `joplin-mcp` is not modified; it runs as a supervised child process.
- Health endpoints are provided by the wrapper, keeping them independent of the MCP transport.
- Joplin and Postgres versions are explicit inputs to the pipeline so compatibility is always tested against a known matrix.
- All write operations are controlled by environment-variable policy flags; delete operations are disabled by default.
- Fixture definitions are authored as Markdown notebook trees and transformed deterministically into seed + expected artifacts.
- `fixtures/fixture.lock` is committed as the reviewed checksum baseline for generated fixture outputs.

---

## Release Model

| Path | Trigger | Gates |
|---|---|---|
| Image release | Git tag `vX.Y.Z` on image changes | Integration tests + supply chain checks |
| Chart release | Git tag `chart-vX.Y.Z` on chart changes | Chart lint + template validation |

- Image and chart versioning are **independent**.
- The Helm chart `values.yaml` exposes `image.repository` and `image.tag` so any image version can be deployed without a chart release.

---

## Current Status

> **Project state: IN PROGRESS**
> Last updated: 2026-04-28

| Area | Status |
|---|---|
| Documentation | ✅ Complete (catalog plus slash-invocable Plan Progress Sync skill, fixture-data Phase 1 contract) |
| Project scaffold | ✅ Complete |
| MCP wrapper | ✅ Complete (skeleton) |
| Dagger pipeline | 🟡 Stage stubs only |
| Helm chart | 🟡 Skeleton only |
| Integration tests | 🟡 Skeleton only |
| Published image | ⬜ Not started |
| Published chart | ⬜ Not started |

---

## Stage Progress

| Stage | Status | Notes |
|---|---|---|
| `fixture-data` | ⬜ Not started | Phase 1 docs aligned: Markdown definitions, deterministic SQL seed target, committed lock baseline, Pirate Fleet Logbook seed theme |
| `build-mcp-image` | ⬜ Not started | |
| `unit-tests` | ⬜ Not started | |
| `build-integration-runner-image` | ⬜ Not started | |
| `build-fixture-tooling-image` | ⬜ Not started | |
| `postgres-service` | ⬜ Not started | |
| `joplin-service` | ⬜ Not started | |
| `mcp-service` | ⬜ Not started | |
| `integration-tests` | ⬜ Not started | |
| `tests` | ⬜ Not started | |
| `pre-publish-checks` | ⬜ Not started | |
| `publish-image` | ⬜ Not started | |
| `publish-chart` | ⬜ Not started | |

---

## Repository Structure

```
joplin-mcp/
├── README.md                   # This file — project overview and status
├── PLAN.md                     # Detailed execution plan and stage contracts
├── SKILLS.md                   # Human-readable skill catalog and usage notes
├── .github/
│   └── skills/
│       └── plan-progress-sync/
│           └── SKILL.md        # Slash-discoverable VS Code skill implementation
├── src/
│   └── joplin_mcp_wrapper/     # Python wrapper application
│       ├── __init__.py
│       ├── main.py             # Entry point; supervises joplin-mcp subprocess
│       └── health.py           # /startupz, /livez, /readyz endpoints
├── dagger/                     # Dagger pipeline — all build and publish logic lives here
│   ├── main.py                 # Pipeline entrypoint (stage stubs)
│   ├── fixture_data.py         # fixture-data stage
│   ├── build_images.py         # build-*-image stages (builds images inside Dagger)
│   ├── services.py             # postgres/joplin/mcp service stages
│   ├── integration_tests.py    # integration-tests stage
│   ├── pre_publish_checks.py   # supply chain / security stage
│   └── publish.py              # publish-image and publish-chart stages
├── fixtures/                   # Checked-in fixture lock and expected outputs
│   ├── fixture.lock            # Checksum manifest — do not edit manually
│   └── expected/               # Expected MCP response files
├── tests/
│   └── integration/            # Integration test suite
├── chart/                      # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
├── pyproject.toml              # Python project metadata and dependencies
└── .vscode/
    └── mcp.json                # VS Code MCP client configuration
```

> There is no `Dockerfile`. The container image is built entirely inside the Dagger pipeline
> using the Dagger Python SDK. `dagger/build_images.py` owns the image build definition.
>
> Files marked as target layout do not exist yet — see PLAN.md for completion state.

---

## Requirements

- Python 3.12+
- [Dagger](https://dagger.io) CLI — all build, test, and publish operations run through Dagger
- Helm 3 (for chart validation only; chart publishing is also handled by Dagger)
- A running Joplin Server instance with Data API enabled on port 22300

---

## Quick Start (once implemented)

```bash
# Run the full image release pipeline
dagger call publish-image --joplin-version=3.x.x --postgres-version=16

# Run integration tests only
dagger call integration-tests --joplin-version=3.x.x --postgres-version=16

# Update fixture lock after intentional data changes
dagger call fixture-data --update-lock
```

---

## Fixture Authoring Model

- Canonical source files live under `fixtures/definitions/` as Markdown files in notebook-like folders.
- Folder hierarchy maps to notebook hierarchy; Markdown files map to notes.
- Fixture generation writes deterministic outputs to `fixtures/seed/` and `fixtures/expected/`.
- `fixtures/fixture.lock` is committed and updated only through `dagger call fixture-data --update-lock`.
- Initial themed fixture catalog is Pirate Fleet Logbook, including Captain Diary entries to validate narrative-style notes.

---

## Links

- [Detailed Execution Plan](PLAN.md)
- [Agent Skills Catalog](SKILLS.md)
- [Plan Progress Sync Skill](.github/skills/plan-progress-sync/SKILL.md)
- [Upstream joplin-mcp package](https://github.com/alondmnt/joplin-mcp)
- [Joplin Server Data API](https://joplinapp.org/api/references/rest_api/)
- [Dagger documentation](https://docs.dagger.io)

---

## Contributing

This repository uses [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
All commit messages must follow the format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Common types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`.

---

## License

This repository is currently licensed under the Mozilla Public License 2.0
(MPL-2.0). See the root [LICENSE](LICENSE) file for the full terms.
