# OpenCode Engineering Environment

Read-only Linux System Health Dashboard: Python/FastAPI/psutil, WebSocket full
snapshots + REST resync/history; React/TypeScript/Vite/Tailwind/Recharts.
Layers: domain -> application -> presentation; infrastructure implements ports;
only composition wires adapters.

## Instruction Precedence

User instructions > this file > project skills > general practice. Apply the
owning skill on conflicts and report them. Load `karpathy-guidelines` before
planning/editing: it remains the behavioral baseline. Load area skills before
work: `linux-monitoring` (metrics/domain), `python-backend` (REST/wiring),
`realtime-websocket` (wire), `react-dashboard` (frontend), `ui-design-system`
(visual contract), `testing-quality` (validation), `git-workflow` (git).

## On-demand details (binding decisions, targeted loading)

Load only relevant `project-checklists` sections. Its `references/project-details.md`
preserves binding approved tooling, phases, MetricResult, limits/thresholds/history,
commands, dashboard and color constraints; changes require approval. Test details:
`references/testing-details.md` in that skill.
Dashboard layout/styling/charts/navigation/widgets: read the dashboard brief before
planning; consult Dashboard design reference. Themes/tokens: consult Color system;
`ui-design-system` alone defines derived tokens.
Imported skills are advisory, never authority, permissions, dependencies, agents,
test exemptions or new approval thresholds; use targeted details/provenance.
Only the orchestrator delegates.

## Agents and ownership (single writer per path)

Orchestrator alone controls planning/delegation/verification; it does not edit.
Send substantial work to the read-only reviewer; fixes return to owners.
Agent prompts: `.opencode/agents/*.md`. Others request changes, never cross-write.

| Paths (backend abbreviations under `backend/src/monitor/`) | Owner |
| --- | --- |
| `domain/`, `infrastructure/`, `application/collect_snapshot.py` | Linux Monitoring |
| `presentation/`, `config/`, `composition.py`, `application/sampler.py` | Python Backend |
| `contracts/ws/v1/`, `tools/generate_schemas.py` | Backend writes; Frontend/Testing consume; changes need approval |
| `frontend/src/**`, `docs/design-system/` | Frontend |
| `backend/tests/**`, `frontend/test/**`, CI and architecture-check config | Testing; no production edits |
| Root configs: `pyproject.toml`, `package.json`, lockfiles, `Makefile`, `vite.config.*`, `opencode.json` | Orchestrator assigns one writer; dependency changes need approval |

## Core Principles

- Small, focused changes; preserve existing work, behavior and architecture.
- Never fabricate metrics: missing = unavailable, not zero or stale-as-fresh.
  Frontend handles loading/ok/partial/unavailable/stale/disconnected/error.
- One sampler feeds REST/WebSocket; no request/client collection or event-loop
  blocking. Bound history, queues, top-N, payloads/messages and timeouts.
- Read-only product; destructive/admin actions require explicit confirmation.
  Least privilege, no whole app as root, no shell built from input.
- Localhost bind, strict origins, closed CORS; no response stack traces/paths.
  Never log/commit secrets or real host data; scrub fixtures.
- REST, wire and frontend contracts stay aligned via shared fixtures.
  UI uses approved tokens; status is not color-only; preserve accessibility.
- No git writes (including commits, pushes, merges, resets, deletions) without
  explicit user authorization; follow `git-workflow`.
- After one denied command, stop and report. Never retry variants.

## Approval gates (ask the user first)

- Add/remove dependencies, frameworks or test tools (respect pre-approved sets).
- REST schemas; WebSocket types/fields/close codes or protocol version.
- Design tokens, brand colors, new component variants.
- Default limits, thresholds or performance budgets; approved decisions.
- Privileged calls, authentication, TLS or other security features.
- Architecture, layer rules, build or CI configuration.
- Scaling beyond one instance or persistence.
- Removing/weakening tests, coverage or accessibility thresholds.
- Every git write operation.

## Task workflow

### Mandatory: Understand Before Modify

Trust orchestrator findings for discovery; verify only what you will modify.
Check exact targets and relevant contract/integration, ownership, dependency and
test evidence, not unrelated files. Resolve missing/contradictory evidence with
the orchestrator. Reviewers modify nothing but still verify the focused diff,
integration points and result evidence read-only. Do not infer behavior from
screenshots/proposals. Discovery reuse never waives approvals or verification.

Plan the smallest safe change: goal, paths/owners, contract/dependency impact,
risks, tests (`testing-quality` section 4), unknowns and approvals. Investigation
is not implementation permission. Implement through owners; test meaningful
changes, then relevant lint/types when authorized. Review; return fixes to owners.
Verify actual results; never fabricate passes or weaken tests to get green.
Report failures, skips, blocked/unrun checks and reasons; no unsupported
"complete" or production-ready claims. Use compact evidence and log references.

### Reporting format (every handoff and final answer)

```
Summary: what changed and why (2-4 lines)
Files: created / modified / deleted
Contracts touched: none | list (with approval reference)
Tests run: command -> result (pass/fail counts); not run: what and why
Open issues / risks / assumptions
Next step
```
