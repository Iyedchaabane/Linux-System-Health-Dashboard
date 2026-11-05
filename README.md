# Linux System Health Dashboard

Read-only, real-time dashboard for Linux host health. A FastAPI backend samples
CPU and memory (plus wired disk and network collectors), publishes JSON
snapshots over WebSocket, and the React frontend renders responsive cards,
history charts, and connection state.

> **Current phase:** backend + frontend foundations are integrated. Live
> WebSocket end-to-end under Playwright remains blocked by a known E2E
> frontend-proxy origin issue (see Limitations).

## Features

- Exposes CPU total/per-core, load average, core count, frequency, plus memory
  total/available/used percent and swap.
- Disk usage (device/total/used/percent) and network cumulative byte counters
  are collected and wired through REST/WebSocket (frontend cards display live).
- Single background sampler; REST and WebSocket serve cached/broadcast data.
- Honest states: `ok`, `partial`, `unavailable`, `stale`, `disconnected`,
  `error`, `loading` — never `0` or last-known-as-fresh.
- Read-only API. Binds to `127.0.0.1` by default; configurable allowed origins.
- 92.97 % backend test coverage (strict mypy + Ruff + import-linter).

## Architecture

- Backend slice: `domain -> application -> presentation` + `infrastructure`,
  composition root in `backend/src/monitor/composition.py`.
- One sampler (`application/sampler.py`) produces snapshots. REST reads from
  sampler.latest(); WS hub consumes them.
- Frontend slice: `domain / infrastructure / application / presentation`
  with theme tokens, Zod schemas, Zustand store, Recharts.
- Shared contract in `contracts/ws/v1/{PROTOCOL.md,schemas,fixtures}`.

## Stack

Backend: Python 3.11–3.13, FastAPI, uvicorn[standard], psutil, pydantic v2,
pydantic-settings, pytest/pytest-asyncio/hypothesis/ruff/mypy.
Frontend: React 18, TypeScript 5, Vite 6, Tailwind 3, Recharts, Zustand, Zod,
Vitest, Playwright.

## Prerequisites
- Python 3.11+ and `uv`.
- Node 20.19+ (or 22.12+), `npm`.
- Linux host (collectors use psutil and Linux interfaces).

## Local development

Backend:
```bash
cd backend
uv sync
# Run in dev mode
uv run uvicorn monitor.presentation.api.app:create_app --factory --reload --port 8080
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Vite dev server proxies `/api` and `/ws` to `http://127.0.0.1:8080`.

## Environment variables (prefix `MONITOR_`)
- `MONITOR_HOST` / `MONITOR_PORT` / `MONITOR_WORKERS`
- `MONITOR_SAMPLE_INTERVAL_SECONDS` (1.0..10.0)
- `MONITOR_MAX_WS_CLIENTS`, `MONITOR_WS_QUEUE_SIZE`, `MONITOR_WS_SEND_TIMEOUT_SECONDS`
- `MONITOR_ALLOWED_ORIGINS` (list; required non-empty when `MONITOR_ENVIRONMENT=production`)
- `MONITOR_ENVIRONMENT` (`development`/`testing`/`production`)
- `MONITOR_DOCS_ENABLED`, `MONITOR_LOG_LEVEL`, `MONITOR_LOG_JSON`
- plus history/process/payload limits listed in `backend/src/monitor/config/settings.py`.

Settings default `host=127.0.0.1`; override to `0.0.0.0` only with reverse proxy.

## Commands

Backend (from `backend/`):
```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src
uv run lint-imports
```

Makefile targets (from repo root):
```bash
make check        # all fast checks
make test         # pytest (default tier)
make lint && make typecheck && make arch
make test-all     # backend + frontend tests
```

Frontend:
```bash
npm run dev
npm run build
npm run test
npm run typecheck && npm run lint
```

E2E:
```bash
npm run test:e2e     # not in package.json; run: npx playwright test
```

## WebSocket Protocol
- Endpoint: `/ws/v1/metrics`, subprotocol `monitor.v1`
- Messages: envelope `{v,type,seq,ts,data}`. Types: `hello`, `snapshot`, `error`, `ping`, `bye` (server→client); `subscribe`, `pong`, `ping`.
- Close codes: 1000, 1001, 1008, 1009, 1011, 1013, 4400, 4401, 4429.
- Full specification: `contracts/ws/v1/PROTOCOL.md`. A rest endpoint exists at `GET /api/v1/snapshot`.

## Quick Start

```bash
./start.sh
```

Additional Makefile commands:
- `make up`, `make down`, `make restart`, `make logs`, `make status`, `make build`, `make test`, `make lint`, `make clean`.

## Security
- Default bind `127.0.0.1`, no wildcard CORS.
- Origin check on WS; empty allowlist rejects browser-origin upgrades (non-browser tooling still allowed).
- Production env (`MONITOR_ENVIRONMENT=production`) requires explicit non-wildcard `allowed_origins`.
- Read-only API (no host mutation).
- Errors never emit stack traces or internal paths.

## Current Limitations
- History tracked in memory (1-hour 1s) for scalar series; no per-client backlog replay.
- No authentication (out of scope for v1); runs as an unprivileged user.
- Only CPU, memory, disk, and network (cumulative) metrics implemented; additional metrics are future phases.

## Project Structure
```
backend/src/monitor/{domain,application,infrastructure,presentation,config,composition.py}
contracts/ws/v1/{schemas,fixtures,PROTOCOL.md}
frontend/src/{domain,infrastructure,application,presentation,app}
tests, e2e, docs/design-system
```

## T2 Status — Running Processes Monitoring

**Status:** PASS WITH NOTES

### Implemented functionality
- Linux process collector (PID, name, CPU percent and RSS); default `process_procfs_path=/proc` reflects the current PID namespace. Compose uses `MONITOR_PROCESS_PROCFS_PATH=/host/proc` with the read-only mount `/proc:/host/proc:ro` for host-process visibility.
- Process group present in shared REST and WebSocket snapshots (`groups.processes`); the dashboard shows at most the existing top 25 processes by CPU, with unknown CPU values last.
- Backend, WebSocket envelope and Zod schema agreed on process row shape, partial/unavailable status and bounds.
- Frontend process panel and table with honest Loading/Unavailable/Stale/Partial states; no client-side truncation or fabrication.

### Verification evidence
Re-verified on the current tree.
- Backend: 358 tests passed, coverage 92.97% (threshold 85%), Ruff check, mypy strict and import-linter clean.
- Frontend: 271 tests passed; typecheck, lint and build clean.
- Browser (isolated Playwright/Chromium): 6 smoke passed + 3 controlled recovery passed; no console errors, no failed REST requests; responsive checks passed.
- Docker: backend and frontend isolated builds passed; REST/WebSocket (hello + snapshot) and schema validation passed; proper desktop/mobile checks.

### Known limitations (not resolved)
- Host-process visibility does not guarantee host-wide scope for all metrics: CPU/memory retain their native psutil view, not cgroup-limit accounting.
- Read-only host procfs is not a confidentiality boundary: process metadata remains exposed, although the adapter collects no command lines or environment variables. Mount it only into a trusted backend; permissions and UID/ptrace restrictions limit reads but do not eliminate metadata exposure.
- Frontend container has no explicit healthcheck.
- Backend `Dockerfile` installs `uv` without a pinned version.
- Nginx master starts as root (workers run as `nginx`).
- Allowed-origin policy could be narrowed (port-less localhost origins are currently accepted).

### Deferred technical debt (needs approval before work starts)
- Pin `uv` version in backend image for reproducibility.
- Narrow acceptable production origins to only configured ports.
- Add frontend container healthcheck.
- Harden/restrict Nginx root-master behavior.
- Broader browser coverage for stale-state suppression and missing process data.

No claim of host-wide monitoring is made.

## License
License file not present (TBD). All code is project-controlled; do not assume an open-source license without confirmation.

## Related Docs
- Ops: `AGENTS.md`
- Phase map: `.opencode/commands/start-phase.md`
