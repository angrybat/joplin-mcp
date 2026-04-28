---
name: plan-progress-sync
description: Review the active conversation against the repository plan, then update PLAN.md, README.md, AGENTS.md, and other affected docs to reflect verified progress, documentation gaps, and valid plan divergence.
argument-hint: summarize the session or name the work you want reconciled with the plan
user-invocable: true
disable-model-invocation: true
---

# Plan Progress Sync

Use this skill after a meaningful work session to reconcile actual progress with the repository plan and companion documentation.

## Primary Goal
Compare the active conversation and repository evidence to [PLAN.md](../../../PLAN.md), then apply only the documentation updates supported by evidence.

## Required Sources
- Active conversation transcript, if available.
- [PLAN.md](../../../PLAN.md)
- [README.md](../../../README.md)
- [AGENTS.md](../../../AGENTS.md)

If transcript context is unavailable, require an operator-provided summary before editing documentation.

## Required Evidence
Use only supported evidence:
- changed files
- test or command output
- explicit implementation details established in the conversation
- commit or PR references, if available

Do not mark any stage complete without evidence.

## Required Updates
Update [PLAN.md](../../../PLAN.md) when evidence supports it:
- front matter: `status`, `last_updated`, `current_phase`, `next_action`
- stage cards: `Status`, `Started`, `Completed`
- Progress Ledger
- Current State Snapshot
- Decision Log only when architecture or release behavior changed

Update [README.md](../../../README.md) to match the plan truth:
- `Last updated`
- Current Status table
- Stage Progress table

Update [AGENTS.md](../../../AGENTS.md) only when process guidance or operating conventions changed.

Update other existing docs when the conversation reveals missing guidance, stale commands, or outdated contracts.

## Divergence Handling
If implementation diverged from the written plan but remains valid:
- update documentation to reflect actual reality
- do not preserve stale sequencing just because it was written first
- add Decision Log rationale only when the divergence changes architecture or release behavior

## Ambiguity Handling
If evidence is incomplete:
- leave the affected stage as in-progress or not-started, whichever is justified
- add a follow-up `next_action`
- do not write completion dates

## Consistency Checks
Before finishing:
- ensure [README.md](../../../README.md) matches [PLAN.md](../../../PLAN.md)
- ensure dates are coherent
- preserve gate rules and fixture-lock rules
- make no functional code edits as part of this skill unless the user explicitly asks for them separately

## Output Format
Respond with:
1. Summary
2. Evidence Checklist
3. Applied Updates
4. Open Follow-ups
