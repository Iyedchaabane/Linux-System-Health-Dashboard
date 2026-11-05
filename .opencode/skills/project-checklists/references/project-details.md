# Project details

Extracted from the existing project instructions. Approved decisions and safety
constraints remain binding; consult only the section relevant to the task.

## Repository layout

Linux System Health Dashboard is a read-only, real-time view of host health.
Backend: Python, FastAPI, uvicorn, psutil and documented `/proc`, `/sys`, cgroup
interfaces. Full snapshots stream over WebSocket; REST serves resync and history.
Frontend: React, TypeScript, Vite, Tailwind CSS, Recharts. Quality: pytest,
Vitest, Playwright and CI gates. Both sides use domain -> application ->
presentation, infrastructure implements ports, composition alone wires adapters.
Skill paths are relative to `backend/` or `frontend/` as applicable.

```
Makefile                                  # check/test/lint/typecheck/arch (Phase 1.0)
backend/pyproject.toml  backend/uv.lock
backend/src/monitor/{domain,application,infrastructure,presentation,config}/  composition.py
backend/tests/{unit,contract,integration,permissions,performance}/  fakes/  fixtures/
frontend/src/{domain,infrastructure,application,presentation,app}/   frontend/test/
contracts/ws/v1/{schemas,fixtures,PROTOCOL.md}
tools/generate_schemas.py   docs/design-system/   deploy/   .github/workflows/
.opencode/{agents,skills,commands}/
```

## Approved decisions

Change only with user approval.

**Tooling**: Python 3.12 for development (CI matrix 3.11 to 3.13), `uv`; Node 20.19+ or 22.12+ (match the installed Vite), `npm`; `Makefile` entry points shared by agents and CI; GitHub Actions for CI.

**Scope and order**: Phase 1 = tooling, domain and ports, wire contract (Pydantic models in `presentation/ws/protocol.py`, generated schemas and fixtures in `contracts/ws/v1/`), settings, architecture checks, minimal CI, review. `collect_snapshot` arrives in Phase 2; the sampler in Phase 3; frontend foundation in Phase 4; uptime and the `system` group in Phase 6.

**Domain**: `MetricResult` is `Ok(value, partial)` or `Unavailable(kind, reason)` with kinds `unsupported`, `permission`, `transient`, `disabled`. New metric groups are additive and do not bump the protocol version.

**Limits**: sample interval default 1 s (min 1 s, max 10 s); 100 clients total, 10 per IP; per-client queue 4 (drop oldest); top-N processes 25 in streams (REST max 100); bind `127.0.0.1`; one uvicorn worker; inbound message 4 KiB; send and handshake timeout 5 s; inbound rate burst 10, refill 2/s; snapshot size budget 16 KiB.

**Thresholds**: warn 80, critical 95 for CPU, memory (based on available) and disk; configurable; state changes require 3 consecutive samples. **History**: 1 hour at 1 s, scalar series only (no process lists).

**Phase 2 scope**: CPU (total, per-core, load average, core count, optional frequency) and memory (total, available, used percent, swap with the `total == 0` case).

## Dashboard design reference

For every dashboard layout, styling, chart, navigation, or widget task:

1. Read `docs/design-system/dashboard-brief.md` before planning or editing.
2. Load `react-dashboard` and `ui-design-system`; load `testing-quality` for implementation validation.
3. Inspect `docs/design-system/dashboard-target.png` when present. It represents the user's **second screenshot**, the desired compact system-monitor layout. `docs/design-system/dashboard-current.png`, when present, represents the **first screenshot**, the previous UI, and is comparison context only.
4. If an image is missing, use the brief's written specification, report that visual comparison is limited, and continue useful work. Never claim to have inspected an absent image or require it for changes already described by the brief.
5. Use the target for composition, density, hierarchy, and chart treatment. Existing approved tokens, metric semantics, accessibility rules, and approval gates still apply. The screenshot does not authorize new colors, component variants, dependencies, API fields, or backend collectors.
6. Inspect available data before implementing a panel. Show an explicit unavailable state for unsupported capabilities; never copy screenshot values or fabricate processes, partitions, sensor readings, or network rates.
7. Validate implemented behavior and, when browser validation is authorized, compare screenshots at the same viewport. Report remaining differences and missing integrations separately from test results.

The brief supplements the instructions and existing skills. Keep it aligned with explicitly approved design decisions; do not create a competing design skill or duplicate token definitions. A request to update documentation alone does not authorize implementing the redesign.

## Skill routing

Load relevant skills before planning/editing in their area, not all skills every task.

| Skill | Trigger / owner |
| --- | --- |
| `karpathy-guidelines` | Behavioral baseline: think before coding, simplicity, surgical changes, goal-driven execution |
| `linux-monitoring` | Collectors, psutil, Linux interfaces, containers, permissions; metric semantics, domain, infrastructure, `MetricResult` |
| `python-backend` | FastAPI, REST, schemas, DI, lifespan, async/blocking, settings; REST contract and backend presentation/wiring |
| `realtime-websocket` | Messages, backpressure, reconnect, heartbeat, close codes, proxies; wire protocol in `contracts/ws/v1/` |
| `react-dashboard` | Components, state, socket client, charts, responsive layout/performance; frontend structure/data flow |
| `ui-design-system` | Colors, tokens, typography, status, component specs, contrast/accessibility; visual contract, section 5 is the only source of color values |
| `testing-quality` | Tests, CI, coverage, flaky tests, bug fixes, completion; strategy, gates, release checklist |
| `git-workflow` | Commits, branches, merges, tags, `.gitignore`, undo/recovery; git safety and conventions |

New metric = monitoring + backend + websocket + dashboard + testing; new widget = dashboard + design-system + testing; protocol change = websocket + both sides + testing.

## Supplementary instruction-only workflows

The orchestrator remains the sole primary project controller. `karpathy-guidelines`
is unchanged and remains the behavioral baseline. Imported skills are advisory,
not new agents, permissions, dependencies, or authority to execute commands:

- `ponytail`: supplementary minimalism; no plugin, automatic prompt injection,
  persistent levels, global mode state, audit/debt commands, or test exemptions.
- `pstack-how`, `pstack-blast-radius`, `pstack-debugging`: investigation,
  change-risk planning, root-cause hypothesis loops. These adapted excerpts do
  not install pstack's router, setup, agents, model choices, or autonomous
  implementation/commit/PR workflows. Reviewers investigate inline; only the
  orchestrator delegates to the existing approved owners.
- `thermo-nuclear-review`: optional deep diff-scoped correctness/security rubric
  for the existing reviewer; findings only, no refactor, autofix, host changes,
  nested agents, or report-file writes. A distinct thermos-derived method,
  not a second pstack distribution.
- `thermo-nuclear-code-quality-review`: separate optional findings-only
  maintainability rubric for canonical-layer reuse, duplication, branching,
  cohesion and type boundaries. No required restructuring, automatic file-size
  blockers, report-file writes, nested delegation or new approval thresholds.

Imported instructions never supersede `AGENTS.md`, project skills, contracts,
permissions, or approval gates. Examples and verification suggestions are not
automatic commands. Run only authorized, bounded checks; otherwise label claims
unverified and request evidence. Provenance, exact pinned sources, adaptations,
licenses, limitations, and rollback guidance are recorded in
`.opencode/skills/ponytail/PROVENANCE.md` and each imported skill's provenance.

## Commands

The `Makefile` is created in Phase 1.0. Until it exists, do not assume these
commands exist; after it exists, read the relevant real targets or use verified
orchestrator evidence. Commands below are guidance, not automatic authorization.

| Purpose | Command |
| --- | --- |
| Everything CI runs (fast tier) | `make check` |
| Backend tests (default tier) | `make test` (`uv run pytest -m "not perf and not soak and not privileged and not quarantine"`) |
| Backend lint and types | `make lint`, `make typecheck` (`uv run ruff`, `uv run mypy --strict`) |
| Architecture | `make arch` (`uv run lint-imports`) |
| Frontend (from `frontend/`) | `npm run test`, `npm run lint`, `npm run typecheck`, `npm run build` |
| E2E | `npx playwright test` (**ask before running**) |

## Color system

Fixed user inputs; do not change without approval. Derived tokens (surfaces,
text, borders, status, chart colors) live **only** in `ui-design-system`
sections 5 and 9, documented in `docs/design-system/tokens.md`. This section
preserves constraints, not a second token definition system.

**Dark theme**: background `#0A0A0A`, primary `#007BA7`, secondary `#FF2D95`.
**Light theme**: background `#E5E4E2` (platinum, decided), brown `#6F4E37` as primary accent, lavender `#E6E0F0` as secondary tint.

Assumption awaiting confirmation: in the light theme, brown is the primary accent and lavender is a tint (selected rows, hover); the secondary accent for text and icons is a derived deeper purple (`#5B4B8A`).

Contrast facts (WCAG 2.x, computed):

| Pair | Ratio | Consequence |
| --- | --- | --- |
| Dark: `#007BA7` on `#0A0A0A` | 4.14 | Not small text; fills, borders, large text only; small text uses derived tint `#3DB8E0` |
| Dark: `#FF2D95` on `#0A0A0A` | 5.71 | OK text; pink-fill labels use `#0A0A0A` (white on pink 3.46 fails) |
| Dark: white on `#007BA7` | 4.78 | OK button labels |
| Light: `#6F4E37` on `#E5E4E2` | 5.86 | OK text/icons |
| Light: white on `#6F4E37` | 7.44 | OK button labels |
| Light: `#E6E0F0` on `#E5E4E2` | 1.01 | Tint only; never carries text/icons |

Status colors are derived per theme; `critical` never reuses brand pink.
Status is never color-only (icon + text label). Every derived pair is verified
by the automated contrast test in both themes.

## OpenCode configuration notes

- `.opencode/agents/`: one file per approved agent; `.opencode/skills/<name>/SKILL.md`:
  on-demand skills; `.opencode/commands/`: `project-status`, `start-phase`.
- Ordered permission rules use broad catch-all first and specific exceptions
  later; last matching rule wins. Preserve existing frontmatter unless changes
  are explicitly approved. Reviewer stays read-only; orchestrator does not edit.
- Permission-change validation requires explicit authorization: check read-only
  `git status` needs no prompt and a write is refused. This is not permission
  to probe at runtime; after one denied command stop and report, never retry.
