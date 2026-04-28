# Fixture Definitions

Canonical fixture inputs are Markdown note files in notebook-like folder trees.
The fixture-data stage transforms these definitions into deterministic artifacts:

- `fixtures/seed/` SQL seed files for Postgres
- `fixtures/expected/` expected MCP responses
- `fixtures/fixture.lock` committed checksum baseline over generated artifacts
- `fixtures/fixture-diff.md` human-readable generation diff on lock regeneration

Repository-wide licensing is defined by the root `LICENSE` file. Fixture
definitions in this directory are covered by MPL-2.0.

## Authoring Rules

1. Use folder structure to represent notebook hierarchy.
2. Use one Markdown file per note.
3. Include YAML frontmatter in every note file.
4. Keep content deterministic: no wall-clock timestamps, random IDs, or
   environment-specific paths.
5. Use sentinel timestamp values in metadata and content examples when needed:
   `2000-01-01T00:00:00Z`.
6. Keep tags and frontmatter lists sorted alphabetically.
7. Use UTF-8 text with LF newlines.

## Frontmatter Contract

Every Markdown note definition must start with frontmatter:

```yaml
---
slug: harbor-welcome-ledger
title: Harbor Welcome Ledger
created: 2000-01-01T00:00:00Z
updated: 2000-01-01T00:00:00Z
tags:
  - fleet
  - logbook
---
```

Required fields:

- `slug`: stable identifier component (lowercase kebab-case)
- `title`: display title for the note
- `created`: sentinel timestamp for deterministic seed generation
- `updated`: sentinel timestamp for deterministic seed generation
- `tags`: optional, sorted alphabetical list

## Initial Seed Catalog (Pirate Fleet Logbook)

Create definitions for these notes as the initial fixture catalog.

1. Notebook `Fleet Command`: `Harbor Welcome Ledger`
2. Notebook `Fleet Command`: `Ship Roster`
3. Notebook `Missions`: `Raid Plan for Black Reef`
4. Notebook `Missions`: `Boarding Checklist`
5. Notebook `Supplies`: `Powder and Shot Inventory`
6. Notebook `Supplies`: `Ration Audit`
7. Notebook `Navigation`: `Tide and Stars Log`
8. Notebook `Navigation`: `Hazard Chart Notes`
9. Notebook `Archive/Old Voyages`: `Storm Passage Report`
10. Notebook `Archive/Old Voyages`: `Port Authority Encounter`
11. Notebook `Captain Diary`: `Day 01 - First Light`
12. Notebook `Captain Diary`: `Day 02 - Mutiny Rumors`
13. Notebook `Captain Diary`: `Day 03 - Calm Before Gale`

The Captain Diary notebook is required to validate narrative chronological notes
in addition to operational logbook-style documents.

## Example Layout

```text
fixtures/definitions/
  Fleet Command/
    harbor-welcome-ledger.md
    ship-roster.md
  Missions/
    raid-plan-for-black-reef.md
    boarding-checklist.md
  Supplies/
    powder-and-shot-inventory.md
    ration-audit.md
  Navigation/
    tide-and-stars-log.md
    hazard-chart-notes.md
  Archive/
    Old Voyages/
      storm-passage-report.md
      port-authority-encounter.md
  Captain Diary/
    day-01-first-light.md
    day-02-mutiny-rumors.md
    day-03-calm-before-gale.md
```

## Validation and Regeneration

- Drift check: `dagger call fixture-data`
- Regenerate and update lock: `dagger call fixture-data --update-lock`

Do not edit `fixtures/fixture.lock` manually.
