---
description: Start an implementation phase with the right skills, agents and approval flow
agent: orchestrator
---

Start the implementation phase requested below. Follow AGENTS.md (principles, approval gates, ownership map, reporting format) and your orchestrator instructions.

Phase request: $ARGUMENTS

(If the request ends with the word "go", skip the approval pause in step 3. Otherwise wait for my approval before any delegation.)

## Live context

Git:
!`git status --short --branch`

## Phase map

Match the request to a phase by number or name. If it does not match, or no phase is given, show me this table and ask which one.

| # | Phase | Skills to load | Agents (in order, one writer at a time) | Must exist when done |
|---|-------|----------------|------------------------------------------|----------------------|
| 0 | Inspect and plan (no edits) | all eight | none | Phased plan with owners, tests, approvals |
| 1 | Contracts and skeleton | `karpathy-guidelines`, `realtime-websocket`, `linux-monitoring`, `python-backend`, `testing-quality` | `@linux-monitoring` (domain, ports, `MetricResult`), `@backend-python` (`contracts/ws/v1/`, package skeleton, settings), `@testing-qa` (pytest config, domain and contract tests) | Fixtures validate against Pydantic models and JSON Schema |
| 2 | Collectors (CPU and memory first) | `karpathy-guidelines`, `linux-monitoring`, `testing-quality` | `@linux-monitoring`, `@testing-qa` | Adapter tests with monkeypatched failures and recorded fixtures; suite passes as non-root |
| 3 | Sampler, REST and WebSocket | `karpathy-guidelines`, `python-backend`, `realtime-websocket`, `linux-monitoring`, `testing-quality` | `@backend-python`, `@testing-qa`, `@code-reviewer` | Single sampler, hub with bounded queues, endpoint per contract, slow-client and leak tests |
| 4 | Frontend foundation | `karpathy-guidelines`, `react-dashboard`, `ui-design-system`, `realtime-websocket`, `testing-quality` | `@frontend-ui`, `@testing-qa` | Tokens for both themes with contrast and parity tests, Zod schemas against shared fixtures, socket client, store, `MetricState` for all seven states |
| 5 | First widgets end to end | `karpathy-guidelines`, `react-dashboard`, `ui-design-system`, `testing-quality` | `@frontend-ui`, `@testing-qa`, `@code-reviewer` | CPU and memory cards live, all states tested, axe clean in both themes, one Playwright journey |
| 6 | More metrics (disk, network, processes) | `karpathy-guidelines`, all relevant | repeat the 2, 3, 5 pattern per metric | Each metric: collector, API field, protocol fixture, widget, tests |
| 7 | Hardening and release | `karpathy-guidelines`, `testing-quality`, `realtime-websocket`, `linux-monitoring` | `@testing-qa`, `@backend-python`, `@code-reviewer` | CI stages, soak and chaos tests, deployment config, release checklist (`testing-quality` section 14) |

Prerequisites: a phase needs the previous phase's "must exist" items. Verify by inspecting the repository, not by assuming. If a prerequisite is missing, say so and propose to do that first. Phase 4 also needs my answer on the light-theme background question in AGENTS.md; if it is unanswered, ask before starting.

## What to do

1. **Inspect.** Read the skills listed for this phase and the current repository state. Report in a few lines what exists and what is missing for this phase.
2. **Plan.** List the tasks for this phase. For each: owner agent, files it may edit, contract impact, tests required (from `testing-quality` section 4), dependencies it would add (none unless approved).
3. **Pause for approval.** Present the plan and wait for my go-ahead. Contract changes, new dependencies and default-limit changes need explicit approval (AGENTS.md approval gates).
4. **Delegate** one task at a time using the briefing template from your instructions. One writer per file; sequence agents that touch related files.
5. **Verify** each result: inspect the diff, confirm the required tests exist and were actually run, check the skill's Definition of Done items for the area.
6. **Review.** Send the phase's work to `@code-reviewer` where the table says so. Route findings to the owning specialist.
7. **Report** in the AGENTS.md reporting format, then recommend the next task. Do not commit unless I ask.

Stop and ask me whenever an approval gate is reached, requirements are ambiguous, a required test fails and cannot be fixed, or two skills conflict.