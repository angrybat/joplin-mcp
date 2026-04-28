# SKILLS.md

## Purpose
This file is the human-readable catalog for reusable repository skills.

The VS Code-discoverable implementation for slash invocation lives in [.github/skills/plan-progress-sync/SKILL.md](.github/skills/plan-progress-sync/SKILL.md).

Use these skills to keep project documentation aligned with actual implementation progress.

---

## Skill: Plan Progress Sync

**Slash command:** `/plan-progress-sync`

**Implementation file:** [.github/skills/plan-progress-sync/SKILL.md](.github/skills/plan-progress-sync/SKILL.md)

### Goal
Review the active conversation, compare verified work against [PLAN.md](PLAN.md), and synchronize progress documentation across required documents.

### Trigger
Use this skill when:
- A work session materially changes implementation state.
- Stage progress changed or evidence was produced.
- Documentation no longer reflects conversation outcomes.
- The implementation path diverged from the exact plan sequence.

### Required Inputs
- Active conversation transcript (primary source).
- Current repository state from [PLAN.md](PLAN.md), [README.md](README.md), and [AGENTS.md](AGENTS.md).
- Evidence from the current session:
  - changed file paths
  - command/test output
  - commit or PR references (if available)

If transcript context is unavailable, require an operator-provided summary before modifying docs.

### Guardrails
- Never claim a stage is complete without evidence.
- Never skip blocking gates in documentation (`tests` and `pre-publish-checks` before `publish-image`).
- Never alter fixture lock policy language.
- Keep updates minimal and deterministic.
- Do not perform functional code refactors in this skill. This skill is documentation synchronization only.

### Update Targets
Required targets:
- [PLAN.md](PLAN.md)
- [README.md](README.md)

Conditional targets:
- [AGENTS.md](AGENTS.md) when conventions or operational instructions changed.
- Other existing docs when conversation evidence shows outdated behavior, commands, contracts, or missing operator guidance.

### Runtime Procedure
1. Extract session facts from the conversation and classify each as: confirmed, ambiguous, or unsupported.
2. Build proposed deltas for [PLAN.md](PLAN.md):
   - front matter (`status`, `last_updated`, `current_phase`, `next_action`)
   - relevant stage status lines (`Status`, `Started`, `Completed`)
   - Progress Ledger append
   - Current State Snapshot rewrite
   - Decision Log append only when architecture or release behavior changed
3. Build corresponding deltas for [README.md](README.md):
   - `Last updated` value
   - Current Status table entries
   - Stage Progress table entries
4. Apply conditional updates to [AGENTS.md](AGENTS.md) and other docs only when required by evidence.
5. Run consistency checks:
   - README status and stage rows match PLAN truth
   - dates are coherent
   - no gate or policy regressions introduced
6. Emit a summary of changes with rationale and evidence references.

### Plan Divergence Policy
If implementation progress diverges from the exact written sequence:
- Do not force docs to match stale assumptions.
- Update plan sequencing/status notes to represent the actual valid path.
- Record rationale in Decision Log only when architecture or release behavior changed.
- Sync README and any impacted guidance docs so contributors follow the current reality.

### Ambiguity Policy
If evidence is insufficient for completion claims:
- Keep the stage as in-progress.
- Add a follow-up `next_action` to resolve the gap.
- Do not write completion dates.

### No-Op Policy
If no substantive progress is detected:
- Make no edits.
- Return a concise explanation of why no update was applied.

### Output Format
Use this structure when reporting a run:

1. `Summary`: one paragraph of what changed.
2. `Evidence Checklist`: files, commands/tests, references.
3. `Applied Updates`: exact doc sections updated.
4. `Open Follow-ups`: unresolved ambiguities or pending actions.

### Invocation Example
"Run Plan Progress Sync for this conversation: compare current implementation discussion to [PLAN.md](PLAN.md), update [PLAN.md](PLAN.md), [README.md](README.md), and any required companion docs, then summarize evidence and deltas."
