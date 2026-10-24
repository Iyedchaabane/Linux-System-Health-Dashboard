---
name: python-backend
description: >
  Build and review Python backend code with FastAPI, Pydantic v2, async I/O and
  WebSockets, following clean architecture. Use this skill whenever the user
  mentions FastAPI, REST endpoints, WebSocket or real-time streaming, Pydantic
  schemas, dependency injection, lifespan or background tasks, ASGI/uvicorn,
  API error handling, CORS, backpressure, broadcasting to clients, or testing an
  async API, even if they only say "backend", "API layer" or "live updates".
  Also use it when integrating blocking libraries (such as psutil) into an async
  service, or when reviewing a service for event-loop blocking, connection
  leaks and unbounded queues.
---

# Python Backend Skill (FastAPI + WebSocket)

Guidance for the API and real-time layer of the **Linux system health
dashboard**. It sits on top of the `linux-monitoring` skill and shares its
clean-architecture layout. Business logic never lives in route handlers.

## 1. Non-negotiable rules

| # | Rule | Why |
|---|------|-----|
| 1 | **Never block the event loop.** Blocking calls (psutil, file reads, `time.sleep`, CPU work) run via `asyncio.to_thread` / `run_in_executor`, or in a plain `def` endpoint. | One blocked call freezes every HTTP request and every WebSocket client. |
| 2 | **Collect once, serve many.** A single background sampler produces snapshots; endpoints and sockets read or subscribe. Never collect per request or per client. | Load must not scale with the number of viewers. |
| 3 | **Every queue, buffer and connection set is bounded.** | Slow clients and traffic spikes must not exhaust memory. |
| 4 | **Routes are thin.** Parse, call a use case, map the result. No psutil, no business logic. | Testability and replaceable delivery layers. |
| 5 | **One consistent error envelope.** No raw exceptions, stack traces or file paths reach clients. | Security and predictable clients. |
| 6 | **Explicit contracts.** Every request, response and WebSocket message has a Pydantic model and a schema version. | Clients and tests can rely on them. |
| 7 | **Own your background tasks.** Created in lifespan, tracked, cancelled and awaited on shutdown. | Prevents orphan tasks and hanging shutdowns. |

## 2. Workflow

1. **Contract first**: define REST resources, WebSocket message types, error envelope and units. Get approval for contract changes (section 12).
2. **Schemas**: Pydantic v2 models in `presentation/schemas/`, separate from domain entities; map explicitly.
3. **Use cases** in `application/` (already exist or are added here), depending on ports only.
4. **Composition root** wires adapters, sampler and hub; expose via FastAPI dependencies.
5. **REST routes**, then **WebSocket endpoint** on top of the hub.
6. **Error handling, logging, limits** (section 8).
7. **Tests** (section 10), then **performance check** (section 9).

## 3. Placement in the architecture

Reuses the `linux-monitoring` layout. Only the `presentation/` and `composition.py` parts are shown.

```
src/monitor/
├── presentation/
│   ├── api/
│   │   ├── app.py              # create_app(), lifespan, middleware, exception handlers
│   │   ├── deps.py             # Depends providers (read from app.state)
│   │   ├── routes/
│   │   │   ├── health.py       # /healthz, /readyz
│   │   │   ├── metrics.py      # /api/v1/snapshot, /api/v1/history, /api/v1/processes
│   │   │   └── system.py       # /api/v1/system (static host info)
│   │   └── errors.py           # ApiError, handlers, error envelope
│   ├── ws/
│   │   ├── endpoint.py         # /ws/v1/metrics
│   │   ├── hub.py              # BroadcastHub, per-client bounded queues
│   │   └── protocol.py         # message models, versioning
│   └── schemas/                # Pydantic request/response models
└── composition.py              # builds container; stored in app.state.container
```

Rules: `presentation` imports `application` DTOs and use cases only. It never imports `infrastructure`. Only `composition.py` does. `import-linter` enforces this.

## 4. FastAPI practices

- **Pydantic v2** (`model_config = ConfigDict(frozen=True, extra="forbid")` for responses; `extra="forbid"` for requests).
- **Lifespan**, not deprecated `@app.on_event`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container(load_settings())      # composition.py
    app.state.container = container
    await container.sampler.start()                   # creates tracked asyncio task
    try:
        yield
    finally:
        await container.hub.close()                   # close sockets with code 1001
        await container.sampler.stop()                # cancel + await
```

- **Dependency injection** via `Depends`, reading from `app.state.container`; tests override with `app.dependency_overrides`.
- `response_model` on every route; return DTOs mapped to schemas, never domain objects or dicts.
- Route naming: plural nouns, versioned prefix `/api/v1`, correct status codes (200, 202, 400, 404, 422, 429, 503).
- Pagination/limits on list endpoints (`limit: int = Query(25, ge=1, le=100)`); allowlist sort keys with `Literal[...]`.
- **Health endpoints**: `/healthz` (process alive, cheap) and `/readyz` (sampler has produced a snapshot recently; returns 503 otherwise).
- Enable OpenAPI with real descriptions and examples; disable `/docs` in hardened deployments via setting.
- Add `GZipMiddleware(minimum_size=1024)` for history responses; keep JSON serialization fast (`ORJSONResponse` optional, needs approval as a new dependency).
- Middleware for cross-cutting only: request id, timing, access log. No business logic.

## 5. Async and blocking-code integration

```python
# application/sampler.py (sketch)
class Sampler:
    def __init__(self, collect: Callable[[], SystemSnapshot], interval: float,
                 on_snapshot: Callable[[SystemSnapshot], None], clock=time.monotonic):
        ...

    async def _run(self) -> None:
        next_tick = self._clock()
        while True:
            started = self._clock()
            try:
                snap = await asyncio.wait_for(
                    asyncio.to_thread(self._collect), timeout=self._interval * 3)
                self._on_snapshot(snap)
            except asyncio.CancelledError:
                raise                                   # never swallow cancellation
            except Exception:                           # isolate failures, keep loop alive
                log.exception("collection failed")
            next_tick += self._interval
            await asyncio.sleep(max(0.0, next_tick - self._clock()))   # fixed cadence, no drift
```

- Collection runs in a thread, with a timeout. A hung collector must not stall the loop.
- Use a bounded thread pool (`ThreadPoolExecutor(max_workers=N)`) if several collectors run in parallel.
- Never `except Exception` around an `await` without re-raising `CancelledError` (it is `BaseException` on 3.8+, but be explicit when catching broadly).
- Prefer `asyncio.TaskGroup` (3.11+) for structured concurrency inside one use case.
- Never create fire-and-forget tasks without storing a reference (they can be garbage-collected mid-run).
- **Uvicorn workers**: each worker process would run its own sampler. Default to **one worker** for this app, or move the sampler to a single leader process. Document this choice.

## 6. WebSocket design

### 6.1 Protocol

- Endpoint: `/ws/v1/metrics`. One JSON text message per event, always with an envelope:

```python
class WsMessage(BaseModel):
    v: Literal[1] = 1
    type: Literal["snapshot", "hello", "error", "ping", "pong"]
    seq: int                     # monotonic per connection, lets clients detect gaps
    ts: float                    # server wall-clock seconds
    data: dict | None = None
```

- Server sends `hello` first (schema version, interval, server limits), then `snapshot` messages.
- Client messages are **allowlisted and validated** (`subscribe` with metric groups, `ping`). Unknown types return an `error` message; do not drop the connection for one bad message, but do after repeated violations.
- Use proper close codes: `1000` normal, `1001` server shutdown, `1008` policy violation (bad origin, auth), `1009` message too big, `1013` try again later (server full).

### 6.2 Hub with bounded per-client queues (backpressure)

```python
class BroadcastHub:
    def __init__(self, max_clients: int = 100, queue_size: int = 4):
        self._clients: set[_Client] = set()
        self._max_clients, self._queue_size = max_clients, queue_size

    def publish(self, message: str) -> None:          # called by sampler, never blocks
        for c in tuple(self._clients):                # copy: set changes during iteration
            if c.queue.full():
                c.queue.get_nowait()                  # drop OLDEST: latest metrics win
                c.dropped += 1
            c.queue.put_nowait(message)

    async def connect(self, ws) -> "_Client": ...     # reject with 1013 when full
    def disconnect(self, client) -> None: ...         # always called in finally
```

Why drop-oldest: for live metrics only the latest value matters; a slow client must never delay others or grow memory.

### 6.3 Endpoint skeleton

```python
@router.websocket("/ws/v1/metrics")
async def metrics_ws(ws: WebSocket, hub: BroadcastHub = Depends(get_hub)):
    if not origin_allowed(ws, settings.allowed_origins):      # check BEFORE accept
        await ws.close(code=1008); return
    client = await hub.connect(ws)                            # accepts or closes with 1013
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(sender(ws, client))                # queue -> socket, send timeout
            tg.create_task(receiver(ws, client))              # validated client messages
            tg.create_task(heartbeat(ws, client, interval=20))
    except* WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(client)                                # no leaked connections
```

- `sender` wraps `ws.send_text` in `asyncio.wait_for(..., timeout=5)`; on timeout, close the client.
- `receiver` enforces a **max message size** and a **message rate limit** per connection.
- Heartbeat: server `ping` message or protocol ping; close connections that miss N pongs (detects half-open TCP).
- Limit total clients, and optionally clients per IP.
- Authentication for WebSockets cannot use custom headers from browsers: use a short-lived token in the query string or first message, validated before streaming. Do not log the token.
- **Reconnection is the client's job**: document exponential backoff with jitter and that the client should resync via `GET /api/v1/snapshot` after reconnect (use `seq` gaps to detect loss). The server does not replay history over the socket by default.

## 7. Service layer and data access

- Use cases are small classes or functions, one responsibility each (`GetLatestSnapshot`, `GetHistory`, `GetTopProcesses`).
- This app has **no database by default**. History is an in-memory bounded ring buffer behind a `HistoryStore` port. **Do not add SQLAlchemy, repositories or Unit of Work unless persistence is a real requirement and approved** (section 12). If persistence is added later, put it behind the same port so nothing above changes.
- Map domain results to schemas in one place (`presentation/schemas/mappers.py`). `Unavailable` states serialize as `{"status": "unavailable", "kind": "...", "reason": "..."}`, never as `0` or omitted silently.

## 8. Error handling, validation, logging

**Error envelope** (same shape for every non-2xx response):

```json
{"error": {"code": "snapshot_not_ready", "message": "No snapshot collected yet", "request_id": "..."}}
```

- Define `ApiError(code, message, status)` subclasses; register handlers for `ApiError`, `RequestValidationError` (map to 422 with safe field messages), `StarletteHTTPException`, and a catch-all `Exception` handler that logs with `request_id` and returns a generic 500.
- Never include exception text, file paths, usernames or stack traces in responses.
- Validate at the edge with Pydantic types (`Field(ge=..., le=...)`, `Literal`, `constr` with patterns). Reject unknown fields. Use allowlists, not blacklist sanitizing.
- **Logging**: structured JSON option; include `request_id`, route, status, duration; never log tokens, auth headers or process command lines. Rate-limit repeated identical errors. Use `logging` with per-module levels.
- Set sensible timeouts: server keep-alive, WebSocket send timeout, collection timeout.

## 9. Performance and resource bounds

- Serialize each snapshot **once**, then fan out the same string to all clients (`hub.publish(json_str)`), instead of serializing per client.
- Use `queue_size` small (2-8) and drop-oldest for metric streams.
- Cap payloads: top-N processes, history `limit`/`window` maximums, response size.
- Cache the latest snapshot in memory (`app.state`); REST reads are O(1).
- Avoid per-request object churn on hot paths; reuse Pydantic `TypeAdapter`s.
- Set `--limit-concurrency` and `--timeout-keep-alive` in uvicorn; use `uvicorn[standard]` (uvloop, httptools, websockets) for WebSocket support. Do not add the `websockets` package separately unless pinned for a reason.
- Targets (tune per host): p95 REST latency under 20 ms on cached endpoints; stable memory over a 24 h soak with 50 connected clients; no growth in task or socket count after repeated connect/disconnect cycles.

## 10. Testing strategy

| Layer | What to test | How |
|-------|--------------|-----|
| Unit | Use cases, mappers, protocol models, hub drop-oldest logic, rate limiter | Pure pytest with fake ports and a fake clock |
| Route | Status codes, schemas, error envelope, validation (422), limits | `httpx.AsyncClient(transport=ASGITransport(app))` with `dependency_overrides` |
| WebSocket | hello then snapshots, `seq` monotonic, bad client message, oversize message, rate limit, close codes, origin rejection | Starlette `TestClient.websocket_connect` |
| Lifecycle | Startup creates sampler; shutdown cancels tasks, closes sockets (1001) | `TestClient` as context manager, or `asgi-lifespan` |
| Concurrency | Slow client does not delay a fast one; queue stays bounded; disconnect removes client | Async tests with fake sockets and `anyio` |
| Leak | Connection and task counts return to baseline after N connect/disconnect cycles | Assert `len(hub._clients)` and `len(asyncio.all_tasks())` |
| Contract | Responses validate against published OpenAPI; schema snapshot unchanged unless approved | Snapshot test of `app.openapi()` |
| Performance | Latency, throughput, memory under 50-200 clients | `locust` or a small asyncio load script, plus `tracemalloc` |
| Security | No stack traces in errors, CORS closed by default, origin check, token not logged | API tests |

Tooling: `pytest`, `pytest-asyncio` (or `anyio` plugin), `httpx`, `pytest-cov` (target **>= 85 % overall, >= 95 % on application and protocol code**; coverage is a floor, not proof), `ruff`, `mypy --strict`, `import-linter`.

Fakes belong at port boundaries. Never fabricate metrics in production code to make a test pass.

## 11. Configuration, security, deployment

- Typed settings (`pydantic-settings`): host, port, `allowed_origins`, `max_ws_clients`, `ws_queue_size`, `sample_interval` (with a floor, see `linux-monitoring`), `log_level`, `docs_enabled`. Env vars override file; validate on startup and fail fast.
- **Bind to `127.0.0.1` by default.** Remote exposure requires explicit config plus authentication (static token or reverse proxy with TLS). Do not build custom user/session systems for this app; that is out of scope unless approved.
- CORS: closed by default, explicit origin list, no `*` with credentials. WebSocket origin checked separately (CORS does not apply to it).
- Security headers via middleware; request size limits; rate limiting on REST (reverse proxy or lightweight in-memory limiter).
- Read-only API. No endpoints that mutate the host.
- Run under systemd or a container as a non-root user; one uvicorn worker (section 5); graceful shutdown timeout configured.
- Pin dependency versions (lockfile); `pip-audit` in CI.

## 12. Operations requiring user approval

Ask before:

- Adding any new external dependency (including ORJSON, Redis, SQLAlchemy, Prometheus client, OpenTelemetry).
- Changing an API or WebSocket contract (fields, types, message types, close codes, versions).
- Implementing authentication, authorization, TLS or other security features.
- Performance-critical optimizations that reduce clarity (custom serialization, multi-process fan-out, shared memory).
- Changing default limits (max clients, queue size, sample interval, payload caps).
- Introducing persistence or a database.

## 13. Optional extensions (only when required)

- **Prometheus**: `prometheus-client`, expose `/metrics` for the app's own health and the host metrics; absent series for unavailable values.
- **Tracing**: OpenTelemetry instrumentation for FastAPI; sampling configured.
- **Multi-instance fan-out**: Redis pub/sub behind the same `publish` interface.
- **Server-Sent Events** as a simpler alternative when clients only receive data.

## 14. Common pitfalls

- Calling `psutil` or file I/O directly in an `async def` route or in the sampler without `to_thread`.
- Collecting metrics inside the WebSocket handler (one collection per client).
- Unbounded `asyncio.Queue()` per client, or `await queue.put` that blocks the broadcaster on a slow client.
- Iterating over the client set while it is being mutated.
- Forgetting `finally: disconnect`, leaking connections after abrupt closes.
- Accepting the socket before checking origin or token.
- Swallowing `CancelledError`, making shutdown hang.
- Using `@app.on_event` and global singletons instead of lifespan and `app.state`.
- Multiple uvicorn workers each running a sampler and showing inconsistent data.
- Returning domain objects or dicts instead of response models.
- Catch-all error handlers that echo `str(exc)` to clients.
- Validating by sanitizing (blacklist) instead of strict allowlists and types.
- Reconnection logic assumed to be on the server.
- Adding a database layer "just in case".

## 15. Definition of done

- [ ] Every REST route and WebSocket message has a Pydantic model, version, and OpenAPI/protocol documentation.
- [ ] No blocking calls on the event loop (verified by test using `asyncio` debug mode or a loop-lag probe).
- [ ] Single sampler; REST and WebSocket serve cached or broadcast data only.
- [ ] Hub bounded: max clients, per-client queue, send timeout, message size and rate limits.
- [ ] Connect/disconnect leak test passes; shutdown cancels all tasks and closes sockets with 1001.
- [ ] Error envelope used everywhere; no internal details leak; tested.
- [ ] `/healthz` and `/readyz` implemented and tested.
- [ ] Binds to localhost by default; CORS and WebSocket origin checks configured and tested.
- [ ] `mypy --strict`, `ruff`, `import-linter` and tests pass in CI; coverage targets met.
- [ ] Soak and load results recorded (latency, memory, task count) against the targets in section 9.
- [ ] Deployment notes document the single-worker decision and privilege model.

## 16. Dependencies

**Core:** `fastapi`, `uvicorn[standard]` (includes WebSocket support), `pydantic` (v2), `pydantic-settings`

**Dev:** `pytest`, `pytest-asyncio` (or `anyio`), `httpx`, `pytest-cov`, `asgi-lifespan`, `locust` (optional), `ruff`, `mypy`, `import-linter`, `pip-audit`

**Not included by default** (approval required, see section 12): `sqlalchemy`, `redis`, `orjson`, `prometheus-client`, `opentelemetry-*`.