# OpenCode Engineering Environment

## Project Overview

Linux System Health Dashboard: a read-only, real-time view of host health.

- **Backend**: Python, FastAPI, uvicorn; metrics via **psutil** and documented Linux interfaces (`/proc`, `/sys`, cgroups)
- **Real-time**: WebSocket stream of full snapshots plus REST for resync and history
- **Frontend**: React, TypeScript, Vite, Tailwind CSS, Recharts
- **Quality**: pytest (Python), Vitest + Playwright (TypeScript), CI quality gates

Architecture is layered on both sides: `domain -> application -> presentation`, with `infrastructure` implementing ports. Only the composition root wires adapters.

### Repository layout (inspect first; the skills' paths are relative to `backend/` or `frontend/`)

```
Makefile                                  # check/test/lint/typecheck/arch (created in Phase 1.0)
backend/pyproject.toml  backend/uv.lock
backend/src/monitor/{domain,application,infrastructure,presentation,config}/  composition.py
backend/tests/{unit,contract,integration,permissions,performance}/  fakes/  fixtures/
frontend/src/{domain,infrastructure,application,presentation,app}/   frontend/test/
contracts/ws/v1/{schemas,fixtures,PROTOCOL.md}     # shared wire contract (generated schemas)
tools/generate_schemas.py   docs/design-system/   deploy/   .github/workflows/
.opencode/{agents,skills,commands}/
```

## Instruction Precedence

1. Direct user instructions in the current session
2. This file (`AGENTS.md`)
3. The skills in `.opencode/skills/<name>/SKILL.md`
4. General best practice

If two skills conflict, apply the **owner** below and report the conflict instead of guessing.

## Skills: when to load which

Load the skill(s) **before** planning or editing in that area.

| Skill | Load when the task involves | Owns |
|-------|-----------------------------|------|
| `linux-monitoring` | Collectors, psutil, `/proc`/`/sys`/cgroups, permissions, unsupported hardware, containers | Metric semantics, `MetricResult` (`Ok`/`Unavailable`), domain and infrastructure layers |
| `python-backend` | FastAPI routes, schemas, DI, lifespan, error envelope, async/blocking, settings | REST contract, app wiring, backend presentation layer |
| `realtime-websocket` | Message types, backpressure, reconnect, heartbeat, close codes, proxies | **Wire protocol** in `contracts/ws/v1/` |
| `react-dashboard` | Components, state, socket client, charts, responsive layout, frontend performance | Frontend structure and data flow |
| `ui-design-system` | Colors, tokens, typography, status look, component specs, contrast, accessibility | **Visual contract** and tokens (section 5 is the only source of color values) |
| `testing-quality` | New tests, CI, coverage, flaky tests, bug fixes, "is it done?" | Test strategy, gates, release checklist |
| `git-workflow` | Commits, branches, merges, tags, `.gitignore`, undo/recovery | Commit and branch conventions, git safety rules |

Combinations: new metric = monitoring + backend + websocket + dashboard + testing; new widget = dashboard + design-system + testing; protocol change = websocket + both sides + testing.

## Agents (full detail lives in `.opencode/agents/*.md`)

- **Orchestrator** (primary): inspects, plans, delegates, verifies, reports. Does not edit source. Contracts first; single writer per file; sends substantial work to the reviewer.
- **Linux Monitoring Specialist**: domain layer, ports, `MetricResult`, collectors. Never fabricates metrics; no root, no shell built from input.
- **Python Backend Specialist**: FastAPI app, settings, error envelope, sampler, WebSocket hub/endpoint, `contracts/ws/v1/`. Never blocks the event loop; no metric collection in handlers.
- **Frontend Specialist**: React app, tokens, socket client, store, charts. Handles all seven data states; tokens only; no fake data.
- **Testing Specialist**: tests, fakes, fixtures, CI config. Never edits production code; never weakens a test to get green.
- **Read-only Code Reviewer**: findings with `file:line` and severity (**Blocker**, High, Medium, Low, Note). Makes no changes.

### Ownership map (single writer per path)

| Paths | Owner | Others |
|-------|-------|--------|
| `backend/src/monitor/domain/`, `infrastructure/`, `application/collect_snapshot.py` | Linux Monitoring | Request changes |
| `backend/src/monitor/presentation/`, `config/`, `composition.py`, `application/sampler.py` | Python Backend | Request changes |
| `contracts/ws/v1/`, `tools/generate_schemas.py` | Python Backend writes; Frontend and Testing consume | Changes need approval |
| `frontend/src/**`, `docs/design-system/` | Frontend | Request changes |
| `backend/tests/**`, `frontend/test/**`, CI config, architecture-check config | Testing | Others describe needed tests |
| Root configs (`pyproject.toml`, `package.json`, lockfiles, `Makefile`, `vite.config.*`, `opencode.json`) | Orchestrator assigns one writer per change | Dependency changes need approval |

## Core Principles

1. **Inspect before editing**; read this file and the relevant skills first.
2. **Small, reviewable changes**; one concern per change; no whole-application generation.
3. **Preserve existing work and architecture**; replace only with justification and approval.
4. **Data integrity**: never fabricate system metrics. Missing data is `unavailable`, never `0`, never a stale value shown as fresh.
5. **Single pipeline**: one sampler produces snapshots; REST and WebSocket serve them. No per-request or per-client collection.
6. **Bounded resources**: history, per-client queues, top-N lists, payload and message limits, timeouts.
7. **Read-only product**; destructive or administrative operations need explicit user confirmation.
8. **Least privilege**; never run the whole application as root.
9. **Contract consistency**: REST schemas, WebSocket protocol and frontend types stay in sync, verified by shared fixtures.
10. **Test affected areas after every meaningful change**; report real results only.
11. **Honest reporting**: state what was run, what passed, what failed, what was not run.
12. **Git**: no commits, pushes, merges, resets or deletions without explicit user authorization; follow `git-workflow`.
13. **Secrets**: never log or commit tokens, credentials or real host data; scrub fixtures.
14. **Security defaults**: bind to localhost, strict origin check, closed CORS, no stack traces or internal paths in responses.

## Approval gates (ask the user first)

- Adding or removing any dependency, framework or test tool (pre-approved sets are listed in each agent file)
- Any change to a REST schema, WebSocket message type/field/close code, or protocol version
- Changing design tokens, brand colors, or adding component variants
- Changing default limits, thresholds or performance budgets listed under Decisions
- Privileged system calls, authentication, TLS or other security features
- Architecture, layer rules, build or CI configuration changes
- Scaling beyond one instance, or adding persistence
- Removing or weakening tests, coverage thresholds or accessibility thresholds
- Every git write operation (see `git-workflow`)

## Decisions (approved by the user; change only with approval)

**Tooling**: Python 3.12 for development (CI matrix 3.11 to 3.13), `uv`; Node 20.19+ or 22.12+ (match the installed Vite), `npm`; `Makefile` entry points shared by agents and CI; GitHub Actions for CI.

**Scope and order**: Phase 1 = tooling, domain and ports, wire contract (Pydantic models in `presentation/ws/protocol.py`, generated schemas and fixtures in `contracts/ws/v1/`), settings, architecture checks, minimal CI, review. `collect_snapshot` arrives in Phase 2; the sampler in Phase 3; frontend foundation in Phase 4; uptime and the `system` group in Phase 6.

**Domain**: `MetricResult` is `Ok(value, partial)` or `Unavailable(kind, reason)` with kinds `unsupported`, `permission`, `transient`, `disabled`. New metric groups are additive and do not bump the protocol version.

**Limits**: sample interval default 1 s (min 1 s, max 10 s); 100 clients total, 10 per IP; per-client queue 4 (drop oldest); top-N processes 25 in streams (REST max 100); bind `127.0.0.1`; one uvicorn worker; inbound message 4 KiB; send and handshake timeout 5 s; inbound rate burst 10, refill 2/s; snapshot size budget 16 KiB.

**Thresholds**: warn 80, critical 95 for CPU, memory (based on available) and disk; configurable; state changes require 3 consecutive samples. **History**: 1 hour at 1 s, scalar series only (no process lists).

**Phase 2 scope**: CPU (total, per-core, load average, core count, optional frequency) and memory (total, available, used percent, swap with the `total == 0` case).

## Task workflow

1. **Inspect** the repo and load the relevant skills.
2. **Plan**: goal, affected paths and owners, contract impact, tests required (`testing-quality` section 4), approval needs.
3. **Implement** in small steps, one writer per file; tests follow each implementation task immediately.
4. **Test**: run affected tiers, then lint and type checks.
5. **Review**: Reviewer checks against skill checklists; fixes go through the owners.
6. **Report** using the format below. Do not commit unless the user asks.

### Reporting format (every handoff and final answer)

```
Summary: what changed and why (2-4 lines)
Files: created / modified / deleted
Contracts touched: none | list (with approval reference)
Tests run: command -> result (pass/fail counts); not run: what and why
Open issues / risks / assumptions
Next step
```

## Commands

The `Makefile` is created in Phase 1.0. Until it exists, agents must not assume these exist; after it exists, read it for the real targets.

| Purpose | Command |
|---------|---------|
| Everything the CI runs (fast tier) | `make check` |
| Backend tests (default tier) | `make test` (runs `uv run pytest -m "not perf and not soak and not privileged and not quarantine"`) |
| Backend lint and types | `make lint`, `make typecheck` (`uv run ruff`, `uv run mypy --strict`) |
| Architecture check | `make arch` (`uv run lint-imports`) |
| Frontend | `npm run test`, `npm run lint`, `npm run typecheck`, `npm run build` (from `frontend/`) |
| End to end | `npx playwright test` (ask before running) |

## Color System

Fixed inputs from the user; do not change without approval. Derived tokens (surfaces, text, borders, status, chart colors) live **only** in `ui-design-system` section 5 and 9 and are documented in `docs/design-system/tokens.md`.

**Dark theme**: background `#0A0A0A`, primary `#007BA7`, secondary `#FF2D95`.
**Light theme**: background `#E5E4E2` (platinum, decided), brown `#6F4E37` as primary accent, lavender `#E6E0F0` as secondary tint.

Assumption awaiting confirmation: in the light theme, brown is the primary accent and lavender is a tint (selected rows, hover); the secondary accent for text and icons is a derived deeper purple (`#5B4B8A`).

Contrast facts agents must respect (WCAG 2.x, computed):

| Pair | Ratio | Consequence |
|------|-------|-------------|
| Dark: `#007BA7` on `#0A0A0A` | 4.14 | Not for small text; use for fills, borders, large text; small text uses the derived tint `#3DB8E0` |
| Dark: `#FF2D95` on `#0A0A0A` | 5.71 | OK for text; labels on pink fills use `#0A0A0A` (white on pink is 3.46, fails) |
| Dark: white on `#007BA7` | 4.78 | OK for button labels |
| Light: `#6F4E37` on `#E5E4E2` | 5.86 | OK for text and icons |
| Light: white on `#6F4E37` | 7.44 | OK for button labels |
| Light: `#E6E0F0` on `#E5E4E2` | 1.01 | Tint only; never carries text or icons |

Rules: status colors are derived per theme and `critical` never reuses the brand pink; status is never color-only (icon + text label); every derived pair is verified by the automated contrast test in both themes.

## OpenCode configuration notes

- `.opencode/agents/` (one file per agent above), `.opencode/skills/<name>/SKILL.md` (seven skills), `.opencode/commands/` (`project-status`, `start-phase`).
- Agent bash permissions: list the catch-all `"*"` **first** and specific patterns after it, because the last matching rule wins. The reviewer is read-only (`edit: deny`, `bash` deny except read-only git, `grep`, `ls`); the orchestrator has `edit: deny`.
- After changing permissions, verify them: ask `@code-reviewer` to run `git status` (should not prompt) and a write command (should be refused).