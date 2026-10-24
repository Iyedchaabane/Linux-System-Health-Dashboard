# OpenCode Engineering Environment

## Project Overview

Linux System Health Dashboard: a read-only, real-time view of host health.

- **Backend**: Python, FastAPI, uvicorn; metrics via **psutil** and documented Linux interfaces (`/proc`, `/sys`, cgroups)
- **Real-time**: WebSocket stream of full snapshots plus REST for resync and history
- **Frontend**: React, TypeScript, Vite, Tailwind CSS, Recharts
- **Quality**: pytest (Python), Vitest + Playwright (TypeScript), CI quality gates

Architecture is clean/layered on both sides: `domain -> application -> presentation`, with `infrastructure` implementing ports. Only the composition root wires adapters.

### Repository layout (adjust if the repo differs; inspect first)

```
backend/src/monitor/{domain,application,infrastructure,presentation,config}/  composition.py
backend/tests/{unit,contract,integration,permissions,performance}/  tests/fakes/  tests/fixtures/
frontend/src/{domain,infrastructure,application,presentation,app}/   frontend/test/
contracts/ws/v1/{schemas,fixtures,PROTOCOL.md}      # shared wire contract
docs/design-system/    deploy/    tools/    .opencode/{agents,skills,commands}/
```

Paths inside the skills are relative to `backend/` or `frontend/` accordingly.

## Instruction Precedence

1. Direct user instructions in the current session
2. This file (`AGENTS.md`)
3. The skills in `.opencode/skills/` (each has `SKILL.md`)
4. General best practice

If two skills conflict, apply the **owner** below and report the conflict instead of guessing.

## Skills: when to load which

Load the skill(s) **before** planning or editing in that area. Most tasks need two or three.

| Skill | Load when the task involves | Owns |
|-------|-----------------------------|------|
| `linux-monitoring` | Collectors, psutil, `/proc`/`/sys`/cgroups, permissions, unsupported hardware, container limits, sampling | Metric semantics, `MetricResult` (`Ok` / `Unavailable`), domain and infrastructure layers |
| `python-backend` | FastAPI routes, schemas, DI, lifespan, error envelope, async/blocking issues, settings | REST contract, app wiring, presentation layer (backend) |
| `realtime-websocket` | Anything on the socket: message types, backpressure, reconnect, heartbeat, close codes, proxies | **Wire protocol** in `contracts/ws/v1/` |
| `react-dashboard` | Components, state, socket client, charts, responsive layout, frontend performance | Frontend structure and data flow |
| `ui-design-system` | Colors, tokens, typography, status look, component specs, contrast, accessibility rules | **Visual contract** and tokens |
| `testing-quality` | Any new test, CI, coverage, flaky test, bug fix, "is it done?" | Test strategy, gates, release checklist |

Typical combinations: new metric = `linux-monitoring` + `python-backend` + `realtime-websocket` + `react-dashboard` + `testing-quality`; new widget = `react-dashboard` + `ui-design-system` + `testing-quality`; protocol change = `realtime-websocket` + both sides + `testing-quality`.

## Agent Responsibilities

### Orchestrator

1. **Inspect first**: read the repo structure, existing code, and relevant skills before planning.
2. **Plan small**: split work into tasks that are independently verifiable (each has a clear check).
3. **Contracts first**: if a task touches a contract (REST schema, WebSocket protocol, tokens, domain entities), plan and get approval for the contract change before any implementation.
4. **Delegate with ownership**: assign each task to the specialist who owns the paths (table below); state the files each agent may edit.
5. **Single writer**: never allow two agents to edit the same file concurrently. Shared files go through one agent at a time.
6. **Review before done**: verify each specialist's report, test evidence, and Definition of Done from the relevant skills.
7. **Boundaries**: do not rewrite the application, generate unrelated file batches, or change architecture without justification and approval.
8. **Does not edit source files** except plans and docs, unless the user assigns it.

### Linux Monitoring Specialist

1. Build and maintain collectors with psutil and documented Linux interfaces behind domain ports.
2. Return `Ok` or `Unavailable(kind, reason)`; handle unsupported hardware, permission denial, partial results, containers.
3. Keep privileged operations out of default paths; no `shell=True`; no shell commands built from external input.
4. **Never fabricate metric values** in production code. Real system data or an explicit unavailable state.
5. Keep one authoritative collection pipeline (single sampler) with bounded history.
6. Provide fixtures and fakes for tests through the Testing Specialist's conventions.

### Python Backend Specialist

1. Implement FastAPI routes, schemas, use-case wiring, lifespan, settings, error envelope.
2. Implement the WebSocket endpoint and hub **exactly per** `realtime-websocket`.
3. Never block the event loop; blocking work goes through `to_thread` with timeouts.
4. Bound everything: clients, queues, payloads, history; default bind `127.0.0.1`; single worker unless approved.
5. Coordinate with the Monitoring Specialist on ports and result types; request changes to domain code instead of editing it.

### Frontend Specialist

1. Implement React/TypeScript components, socket client, store, charts per `react-dashboard`.
2. Follow `ui-design-system` for every color, size and state; no raw values in components.
3. Every widget handles: loading, ok, partial, unavailable, stale, disconnected, error.
4. Validate server messages with Zod against the shared fixtures; never display fake data for unavailable metrics.
5. Responsive, accessible, themed (light and dark) with the color specification below.

### Testing Specialist

1. Add unit, contract, integration, end-to-end and frontend tests per `testing-quality`.
2. Use **fakes at port boundaries** (test code only) and recorded real fixtures; never put fabricated data in production code.
3. Cover edge cases: missing hardware support, permission errors, process termination mid-iteration, WebSocket disconnects, counter resets.
4. **Report results accurately.** A task with failing required tests is not done. Never delete, skip, or weaken a test to get green without user approval; quarantine rules are in `testing-quality`.
5. May edit tests, fixtures, fakes, and CI config; edits to production code go through the owning specialist.

### Read-only Code Reviewer

1. Review correctness, maintainability, performance, security, accessibility, contract consistency, and regressions against the skills' checklists.
2. Provide `file:line` references for every finding.
3. Classify severity: **Blocker** (breaks rules or data integrity), **High**, **Medium**, **Low**, **Note**.
4. Make no changes. Do not implement fixes unless the user explicitly reassigns the role.

### Ownership map (single writer per path)

| Paths | Owner | Others |
|-------|-------|--------|
| `backend/src/monitor/domain/`, `application/collect_*`, `sampler`, `infrastructure/` | Linux Monitoring | Request changes |
| `backend/src/monitor/presentation/`, `config/`, `composition.py`, backend packaging | Python Backend | Request changes |
| `contracts/ws/v1/` | Python Backend writes schemas; Frontend and Testing consume | Changes need approval |
| `frontend/src/**`, `docs/design-system/` | Frontend | Request changes |
| `backend/tests/**`, `frontend/test/**`, CI config | Testing | Others add tests in their own area only when assigned |
| Root configs (`pyproject.toml`, `package.json`, lockfiles, `vite.config.*`, `opencode.json`) | Orchestrator assigns one writer per change | Dependency changes need approval |

## Project Instructions

### Core Principles

1. **Inspect before editing**: read existing files and the relevant skills first.
2. **Small, reviewable changes**: one concern per change; no whole-application generation.
3. **Preserve existing work and architecture**; replace only with clear justification and approval.
4. **Data integrity**: never fabricate system metrics. Missing data is `unavailable`, never `0`, never a stale value shown as fresh.
5. **Single pipeline**: one sampler produces snapshots; REST and WebSocket serve them. No per-request or per-client collection.
6. **Bounded resources**: history ring buffer, per-client queues, top-N lists, payload and message limits, timeouts.
7. **Read-only product**: normal monitoring never mutates the host. Destructive or administrative operations require explicit user confirmation.
8. **Least privilege**: never run the whole application as root; privileged features are opt-in, isolated, documented.
9. **Contract consistency**: REST schemas, WebSocket protocol, and frontend types stay in sync, verified by shared fixtures.
10. **Test affected areas after every meaningful change**, and report real results.
11. **Honest reporting**: state what was run, what passed, what failed, what was not run.
12. **Git and destructive actions**: no commits, pushes, force operations, file deletions outside the task, or dependency removals without explicit user authorization.
13. **Secrets**: never log or commit tokens, credentials, or real host data; scrub fixtures.
14. **Security defaults**: bind to localhost, strict origin check, closed CORS, no stack traces or internal paths in responses.

### Approval gates (ask the user first)

- Adding or removing any dependency, framework, or test tool
- Changing any REST schema, WebSocket message type/field/close code, or protocol version
- Changing design tokens, the color system, or adding component variants
- Changing default limits (clients, rates, sizes, sample interval, thresholds) or performance budgets
- Adding privileged system calls, authentication, TLS, or other security features
- Changing architecture, layer rules, or build/CI configuration
- Scaling beyond one instance or adding persistence
- Removing or weakening tests, coverage thresholds, or accessibility thresholds

### Task workflow

1. **Inspect** repo and load relevant skills.
2. **Plan**: goal, affected paths and owners, contract impact, tests required (from `testing-quality` section 4), approval needs.
3. **Implement** in small steps, owner by owner, one writer per file.
4. **Test**: run the affected tiers, then lint/type checks for touched areas.
5. **Review**: Reviewer checks against skill checklists; fix findings through owners.
6. **Report** using the format below.

### Reporting format (every specialist handoff and final answer)

```
Summary: what changed and why (2-4 lines)
Files: created / modified / deleted
Contracts touched: none | list (with approval reference)
Tests run: command -> result (pass/fail counts); not run: what and why
Open issues / risks / assumptions
Next step
```

### Commands

Agents must **read `pyproject.toml`, `package.json`, and CI files to find the real commands** and must not assume these exist. Typical set to confirm and record here once verified:

| Purpose | Command (confirm) |
|---------|-------------------|
| Backend tests (default tier) | `pytest -m "not perf and not soak and not privileged and not quarantine"` |
| Backend lint/types | `ruff check . && ruff format --check . && mypy --strict src` |
| Architecture check | `lint-imports` |
| Frontend tests | `npm run test` (Vitest) |
| Frontend lint/types | `npm run lint && npm run typecheck` |
| E2E | `npx playwright test` |
| Dev servers | backend `uvicorn ...`, frontend `npm run dev` (confirm and document) |

## Color System (fixed inputs from the user)

These values are specified by the user and must **not be changed** without approval. Derived tokens (surfaces, text, borders, status colors, chart colors) are created in `ui-design-system` around them and documented in `docs/design-system/tokens.md`.

**Dark Theme**
- `#0A0A0A` Background
- `#007BA7` Primary/Accent
- `#FF2D95` Secondary/Accent

**Light Theme**
- `#6F4E37` Background
- `#E5E4E2` Primary/Accent
- `#E6E0F0` Secondary/Accent

Contrast findings (WCAG 2.x, computed), which the Frontend Specialist must respect:

| Pair | Ratio | Consequence |
|------|-------|-------------|
| Dark: `#007BA7` text on `#0A0A0A` | 4.14 | Below 4.5 for small text. Use for fills, borders, icons, large text (3:1 passes). Small primary-colored text needs a derived lighter tint. |
| Dark: `#FF2D95` text on `#0A0A0A` | 5.71 | OK for text |
| Dark: white text on `#007BA7` | 4.78 | OK for button labels |
| Dark: white text on `#FF2D95` | 3.46 | Fails. Use `#0A0A0A` text on pink fills (6.06). |
| Light: `#6F4E37` is a mid-dark brown (luminance 0.09) | - | Dark text on it fails (about 2.4 to 2.8). Text must be light. |
| Light: `#FFFFFF` / `#E5E4E2` / `#E6E0F0` on `#6F4E37` | 7.44 / 5.86 / 5.77 | All pass for text |

Rules:
- Status colors (`ok`, `warn`, `critical`, `info`) are derived **per theme** to pass contrast on that theme's surfaces. `critical` must never reuse the secondary pink, so a brand accent is not mistaken for an alert.
- Status is never color-only: icon + text label always (`ui-design-system` section 6).
- Verify every derived pair with the automated contrast test for **both** themes.
**Decision (2026-10-25)**: The Light Theme uses **platinum `#E5E4E2` as the page background** with dark text (`#6F4E37` as primary accent, 5.86:1 contrast). The lavender `#E6E0F0` is a subtle surface tint. This makes "light" an actual light page. The brown `#6F4E37` is repurposed as the primary accent color for the light theme.

## Files Created

This project was initialized with the following OpenCode configuration:
- `opencode.json` - Main OpenCode configuration with agent settings
- `AGENTS.md` - This document with agent responsibilities and project instructions
- `.opencode/agents/` - Agent configuration files (one per role above; tool permissions should match: Reviewer read-only, Orchestrator no source edits)
- `.opencode/skills/<skill-name>/SKILL.md` - The six skills: `linux-monitoring`, `python-backend`, `realtime-websocket`, `react-dashboard`, `ui-design-system`, `testing-quality`
- `.opencode/commands/` - Reusable project commands (suggested: `/check` runs the default test and lint tiers, `/review` invokes the Reviewer, `/contract-check` validates fixtures against schemas)
## Tooling Decisions

**Package Managers**
- Python: **uv** (pyproject.toml native, lockfile, fast resolution)
- Node: **npm** (standard, works with Vitest/Playwright without extra config)

**Minimum Runtime Versions**
- Python: **3.11+** (required for `asyncio.TaskGroup`, `except*` exception groups, `tomllib`)
- Node: **20+** (current LTS at project start; Vite, Vitest, Playwright supported)

These are recorded here so all agents use the same tooling. Changing them requires approval (AGENTS.md approval gates).
