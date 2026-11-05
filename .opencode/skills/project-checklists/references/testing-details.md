# Detailed testing checklists

Use only the relevant sections alongside `testing-quality` (strategy/gates owner)
and the skill owning the area under test. These checklists authorize no new
dependencies, CI/build changes, live external services or host mutation.

## Targeted inspection

Trust orchestrator findings for discovery; verify only what you will modify.
Before implementing tests, verify applicable targets/integration evidence only:

1. `AGENTS.md` and relevant project instructions.
2. Assigned test structure and relevant existing tests/conventions.
3. Relevant test configuration and installed dependency/lockfile evidence when needed.
4. Installed frameworks; do not assume a runner or command exists.
5. Actual contract/integration evidence for this area, not every application layer.
6. API contracts and monitoring data formats used by the tests.

Resolve missing/contradictory findings with the orchestrator. Prefer existing
tools; recommend new tools only for clear benefit and request approval before
installing. Inspect relevant `package.json` and test configuration for frontend
work, not unrelated manifests for every task.

## Testing architecture

Prioritize regressions and critical behavior; choose the cheapest useful layer.

- **Unit:** CPU/memory transformations, disk/network rate math, missing/invalid
  values, Python utilities/services, cards/tables, byte/percent/rate/time formatting.
- **Integration:** routes/services, validation/serialization, WebSocket updates,
  hooks/API responses, components updating metrics, error propagation.
- **E2E:** when an appropriate tool exists and execution is authorized, cover
  opening the dashboard, sidebar navigation, theme switching, live data,
  disconnect and recovery. Do not introduce browser automation for low-value cases.
- **Contract:** real endpoint paths/methods, request/response fields/types,
  optional/null values, errors and WebSocket messages agree across frontend
  and backend. Never invent or silently change contracts; use shared fixtures.

## Backend testing

Use the existing Python setup: pytest, pytest-asyncio when needed, unittest.mock
or existing mocks, FastAPI TestClient or the existing async HTTP client, pytest-cov
only when available/useful. If no setup exists, recommend pytest/pytest-asyncio;
recommendations do not authorize installation.

### API endpoints

- Successful requests/status codes, response structure and field types.
- Invalid parameters/request validation, unavailable data, expected error envelope.
- Service exceptions, dependency overrides and isolation from live system state.
- Use actual routes and schemas, never invented endpoints.

### Linux metrics

Cover CPU, memory, disk capacity/utilization, network counters/rates, processes,
sensors, system information and uptime as applicable to the assigned feature.
Mock psutil/OS calls; deterministic tests must not depend on host load, processes
or sensor availability. Test valid/empty/missing/unsupported/exceptional results,
zero denominators (including no swap), counter resets, units/types/bounds.
Unavailable hardware must not crash unrelated features. Optional metrics follow
the actual contract. Live smoke checks use shape/range, never exact changing values.

### Permissions and process races

Simulate protected reads/permission errors, disappearing processes, invalid or
inaccessible PIDs, unsupported facilities and OS exceptions. Ordinary unit tests
must not require root. Truly privileged tests are isolated, documented and opt-in.

### Async and background tasks

Verify startup/shutdown, cancellation, periodic collection exceptions, resource
cleanup and duplicate-worker prevention where applicable. Await cleanup; do not
leave background tasks running.

## WebSocket testing

Use the actual endpoint/contract. Cover connection establishment, initial and
subsequent messages, serialization, missing/malformed data, disconnect cleanup,
collection failures with connected clients, supported concurrency, cancellation,
shutdown and reconnect at the appropriate client/integration layer.

Verify no leaked connections; one disconnected client must not break others.
Failed collection cycles must not permanently stop updates unless intentional.
Messages contain only specified fields. Use bounded deterministic tests, never
unbounded loops or uncontrolled load.

## Frontend testing

Use the existing framework. If absent, recommend Vitest for Vite, React Testing
Library, user-event and MSW where useful; obtain required approval first. Do not
introduce Jest alongside Vitest without compelling justification/approval.

### Components

Verify cards/charts, loading/empty/unavailable/error and the applicable seven
metric states, process tables/sorting, theme presentation, page navigation,
accessible names and keyboard interactions. Assert user-visible behavior, not
implementation details.

### Data, hooks and sockets

Cover API responses, loading/error transitions, connection lifecycle, valid and
malformed messages, disconnect/reconnect, unmount cleanup, duplicate-connection
prevention, stale/missing data, bounded chart history and frequent updates.
Mock network/browser APIs; ordinary unit tests do not require a real backend.

### Charts and accessibility

Assert metric values/units, empty/missing data, message-driven updates, labels
and accessible descriptions. Avoid fragile snapshots alone. Visual regression
is appropriate when supported or justified and approved, not an automatic new tool.
Check semantic HTML, accessible names, keyboard navigation, visible focus,
appropriate status announcements and text/icon cues independent of color.
Use automated accessibility tools only when configured or explicitly approved.

## Fixtures and mock data

Use representative deterministic fixtures in existing project test locations:
typical CPU/memory, empty processes, vanished processes, missing sensors,
disk/network failures, valid/invalid responses, missing message fields and
disconnected backend. Reuse fixtures without needless duplication; match schemas.
Never include secrets, personal data or sensitive real host information. Never
modify real settings/files. Clean temporary files/resources. Do not create a
competing fixture structure without a reason.

## Reliability, performance and security

- Avoid timing-sensitive assertions and arbitrary sleeps. Prefer events,
  synchronization and bounded timeouts. Investigate flaky tests; never silently
  retry failed assertions to hide defects.
- Where justified, cover collection overhead, bounded history, large process
  lists, socket cleanup, excessive calls and unnecessary frontend renders.
  Thresholds must be environment-aware; local unit tests do not prove production
  performance guarantees.
- Check errors do not leak secrets/internal details, tests do not log credentials
  or private configuration, invalid input is rejected, fixtures cannot target
  real external systems, and destructive operations require explicit authorization.
  Never print environment variables, access tokens, passwords or private keys.

## Coverage and quality

Prioritize rate math, API/wire contracts, recovery, frontend transitions, cleanup,
unsupported hardware, permission failures and recent regressions. When available,
report measured coverage and important uncovered branches; distinguish line
coverage from behavioral confidence. Never add low-value tests solely for a
percentage. Never edit production code to improve scores or make tests pass;
report defects and route them to the owning specialist.

## Execution and automation

1. Verify intended behavior, exact targets and relevant conventions.
2. Write focused tests; run the smallest relevant subset first.
3. Diagnose test defects versus application defects versus environment failures.
4. Run broader tests, relevant type/lint/build checks only when supported/permitted.
5. Review session changes for unrelated modifications and report actual results/gaps.

Use supported commands only. Do not modify production data, run destructive
commands or test live external services automatically. Maintain existing CI
conventions; do not add/modify workflows unless requested or clearly assigned,
and obtain approval for build/CI configuration changes. When automation is
requested, consider backend/frontend change checks, isolated integration,
coverage/report artifacts and actionable failures. Use staging/test environments
for load/integration; no production load without explicit authorization.

## Ownership and reporting

Follow the current layout; example test locations are not mandates to create
`tests/unit`, `tests/integration`, `tests/api`, `tests/frontend`, `tests/fixtures`
or `test-reports`. Testing owns `backend/tests/**`, `frontend/test/**`, fixtures,
test configuration and assigned CI/architecture-check configuration. No production
edits; report blocking production defects and coordinate through the orchestrator
with backend/frontend/monitoring owners for clarification.

Preserve functionality and conventions, make small changes, respect OpenCode
approval prompts. Never fabricate results, call skipped/failed/unrun tests passing,
suppress errors, remove failing tests, weaken assertions or change expected
behavior without justification/approval. No commits/pushes without user request.

Use the AGENTS report format: changed test files, exact commands, actual
passed/failed/skipped/blocked counts, measured coverage only if collected,
issues and remaining gaps. Use compact evidence and log references, not full
raw output. If tests were not run, explicitly say why. A green suite alone
never establishes full testing or production readiness.
