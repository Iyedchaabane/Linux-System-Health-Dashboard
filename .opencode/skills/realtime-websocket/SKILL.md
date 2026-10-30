---
name: realtime-websocket
description: >
  Design, implement and review the WebSocket protocol and live-streaming
  behavior of a real-time system health dashboard: message contract, delivery
  semantics, backpressure, heartbeat and staleness, reconnection, close codes,
  rate limiting, authentication, compression, proxies and shutdown. Use this
  skill whenever the user mentions WebSocket, live or real-time metric
  streaming, push updates, streaming protocol, message format or schema,
  reconnect or backoff, dropped or out-of-order messages, slow clients,
  broadcasting, heartbeat/ping, wss or proxy upgrade problems, or "the
  dashboard stops updating", even if they do not say "protocol". Also use it
  before changing any message field, message type or close code.
---

# Real-time WebSocket Skill

This skill is the **canonical owner of the wire protocol** between the FastAPI
backend (`python-backend`) and the React client (`react-dashboard`). Those two
skills describe how each side is built; this one defines what travels between
them. If they disagree with this file, this file wins and the other must be
updated (after approval, section 14).

## 1. Non-negotiable rules

| # | Rule | Why |
|---|------|-----|
| 1 | **One contract, one source of truth.** Pydantic models generate JSON Schema; fixtures are shared; Zod schemas on the client are tested against the same fixtures. | Prevents silent drift between server and client. |
| 2 | **Messages are full snapshots, not deltas** (default). Latest state wins. | Dropped or reordered messages then need no repair, which makes backpressure and reconnects trivial. |
| 3 | **Never block the broadcaster.** `publish` is non-blocking; each client has a small bounded queue; overflow drops the oldest. | A slow client must not delay others or grow memory. |
| 4 | **Every limit is explicit**: clients, queue size, message size, message rate, handshake time, idle time. | Unbounded anything eventually becomes an outage. |
| 5 | **Silence is a signal.** The client treats "no message within 2x interval" as stale and reconnects. Do not trust TCP to report a dead peer. | Half-open connections are common on mobile, NAT and proxies. |
| 6 | **Validate everything crossing the boundary, both directions.** Unknown types, oversized or malformed messages never reach business logic. | Security and robustness. |
| 7 | **Reconnect is the client's job; resync uses REST.** The server never replays a backlog over the socket. | Keeps the server stateless per client and simple. |
| 8 | **Never fabricate data on the wire.** Unavailable metrics are sent as `unavailable` with a reason, never `0`, `null` without status, or last-known values presented as fresh. | Same honesty rule as the rest of the system. |

## 2. Scope, transport and library choice

- **Server**: FastAPI/Starlette `WebSocket` on **uvicorn** (`uvicorn[standard]` provides the WebSocket implementation). Do not run a second, standalone WebSocket server, and do not add Socket.IO (it is a different protocol with its own framing; browsers' native `WebSocket` cannot talk to it).
- **Browser client**: native `WebSocket` API wrapped in `infrastructure/ws/`.
- **Python client** (the `websockets` package) exists **only** for integration tests, load tests and CLI tools under `tools/` or `tests/`; it is a dev dependency, not part of the app.
- This corrects the idea of "use `websockets` for the server": the server's library is whatever uvicorn provides, configured through uvicorn options (section 8).
- One endpoint: `/ws/v1/metrics`. Version lives in the path **and** in every message (`v`).
- Transport security: `wss://` whenever not on localhost. Per-message encryption, signing or "integrity" fields are unnecessary on top of TLS and add complexity without benefit.

## 3. Repository layout for the contract

```
contracts/ws/v1/
├── PROTOCOL.md            # human-readable spec (generated sections + prose)
├── schemas/               # JSON Schema generated from Pydantic (committed)
│   ├── server_message.schema.json
│   └── client_message.schema.json
└── fixtures/              # real, recorded examples; used by BOTH test suites
    ├── hello.json  snapshot_ok.json  snapshot_partial.json
    ├── snapshot_unavailable.json  error_invalid_message.json  bye.json
src/monitor/presentation/ws/   # server: protocol.py, hub.py, endpoint.py
frontend src/infrastructure/ws/ # client: schemas.ts (Zod), MetricsSocket.ts, backoff.ts
tests/contract/                 # server validates fixtures against Pydantic + schema
frontend test/contract/         # client validates the same fixtures against Zod
```

CI fails if the generated schema differs from the committed one without an approved version bump.

## 4. Protocol v1

### 4.1 Envelope (every message, both directions)

```json
{ "v": 1, "type": "snapshot", "seq": 1042, "ts": 1767225600.512, "data": { } }
```

| Field | Type | Rules |
|-------|------|-------|
| `v` | int | Protocol version; mismatch is a hard error (4400). |
| `type` | string | Allowlisted (4.2). Unknown types are rejected. |
| `seq` | int | Server messages only. Starts at 0 per connection, increments by 1 per message **attempted**; gaps mean messages were dropped for this client. |
| `ts` | float | Server wall-clock seconds (display only). Staleness is measured on the client with its own monotonic clock. |
| `data` | object or null | Type-specific payload. `extra="forbid"` on the server side; the client ignores unknown **additive** fields for forward compatibility. |

Subprotocol: client offers `Sec-WebSocket-Protocol: monitor.v1`; server echoes it, or closes with 4400 if unsupported.

### 4.2 Message types

| Direction | `type` | Purpose | `data` |
|-----------|--------|---------|--------|
| S->C | `hello` | First message after accept | `{interval_ms, max_message_bytes, groups: [...], server_time, limits: {...}}` |
| S->C | `snapshot` | Full state for subscribed groups | `{groups: {cpu: ..., memory: ..., ...}, meta: {dropped_since_last?: n}}` |
| S->C | `error` | Recoverable protocol error | `{code, message}` (safe text only) |
| S->C | `ping` | Optional idle probe (only if no snapshot sent recently) | `null` |
| S->C | `bye` | Orderly close notice | `{reason}` (e.g. `shutdown`) |
| C->S | `subscribe` | Choose metric groups | `{groups: ["cpu","memory"]}` |
| C->S | `pong` | Reply to `ping` | `null` |
| C->S | `ping` | Client liveness probe | `null` (server replies `pong`) |

`snapshot.data.groups.<name>` uses the shared metric shape: `{"status":"ok","value":...,"partial":false}` or `{"status":"unavailable","kind":"permission","reason":"..."}`. Defaults: subscribed to all groups until the client says otherwise.

Any new type, new required field, renamed or removed field is a **contract change** (section 14).

### 4.3 Delivery semantics

- **At-most-once, latest-wins, per-connection ordered.** No acknowledgements, no retransmission.
- Because snapshots are complete state, a gap in `seq` does **not** corrupt the display. The client simply renders the newest snapshot.
- Gaps matter only for **history charts**: the client marks the gap as missing samples and, if it needs the missing interval, fetches `GET /api/v1/history?from=...` (REST) once, never in a loop.
- When the server dropped messages for a client, the next snapshot carries `meta.dropped_since_last` (optional, additive).
- Duplicate or out-of-order `seq` on the client: ignore anything with `seq <=` the last accepted.
- Deltas, batching of several snapshots in one frame, or priority classes are **not** part of v1; adding them requires approval and a version bump.

### 4.4 Connection state machine

```
CONNECTING -> OPEN(hello received) -> STREAMING -> (stale | error | close) -> RECONNECTING -> CONNECTING
                                                                 \-> FATAL (policy/auth/version) : no retry
```

Server handshake order: check `Origin` and auth **before** `accept`; accept; send `hello` within the handshake timeout; then stream.

## 5. Close codes

| Code | Meaning | Client action |
|------|---------|---------------|
| 1000 | Normal closure | Reconnect only if the user did not close. |
| 1001 | Server going away (shutdown/restart) | Reconnect with jittered delay (avoid thundering herd). |
| 1008 | Policy violation (bad origin) | **Fatal**: show message, no retry loop. |
| 1009 | Message too big | Fatal for that payload; fix the client; limited retry. |
| 1011 | Internal server error | Backoff reconnect. |
| 1013 | Try again later (server full) | Reconnect with longer backoff (start >= 10 s). |
| 4400 | Unsupported protocol version or repeated invalid messages | **Fatal**: show "client outdated" or bug message. |
| 4401 | Authentication missing, invalid or expired | Fatal until a new token is available; no blind retries. |
| 4429 | Message rate limit exceeded | Backoff reconnect, slow down. |

Codes 4xxx are application-defined (range 4000-4999). Do not repurpose a code once published. Close reasons are short, safe text (no internals, max 123 bytes).

## 6. Server behavior

(Code sketches for the hub and endpoint live in `python-backend` section 6; the rules below are the contract they must satisfy.)

- **Single sampler, single serialization.** Snapshot JSON is serialized once per interval per group-set and the same string fans out to all matching clients.
- **Per-client bounded queue** (default size 2-8) with **drop-oldest**; count drops per client and expose them in meta and in server metrics.
- **Send timeout** (default 5 s) on each `send`; timeout closes the client with 1013 or 1011.
- **Limits** (all configurable, all enforced): max total clients (default 100), max clients per IP (default 10), max inbound message size (default 4 KiB, since clients only send tiny commands), inbound rate limit, handshake timeout (default 5 s), idle timeout (default 60 s without any inbound frame is acceptable only because snapshots keep flowing; use protocol ping for dead-peer detection instead).
- **Inbound rate limit**: token bucket, e.g. burst 10, refill 2 per second. Exceeding it sends `error` once, then closes with 4429 on persistence.
- **Heartbeat**: the snapshot stream is the heartbeat. Send an app-level `ping` only if nothing was sent for `interval x 3` (for example when a group set is empty). Rely on uvicorn's protocol-level ping/pong (`--ws-ping-interval`, `--ws-ping-timeout`) to reap dead peers. Browsers answer protocol pings automatically but cannot observe them, which is why the client uses message silence for staleness.
- **Authentication** (only when approved/enabled): validate a short-lived token **before** `accept`. Browsers cannot set custom headers on WebSocket, so use the `Sec-WebSocket-Protocol` subprotocol trick or a one-time ticket in the query string obtained from an authenticated REST call (single-use, expires in under 60 s). Never log tokens or full URLs with tokens; never accept long-lived secrets in the query string.
- **Origin check** against an allowlist (CORS does not protect WebSockets).
- **Graceful shutdown**: stop accepting, send `bye`, close all with 1001, then cancel tasks. Clients will reconnect, so the server relies on **client jitter** to avoid a reconnect stampede.
- **Logging**: connect/disconnect with client id, reason, duration, messages sent, dropped count; rate-limit repeated errors; never log payloads or tokens.

## 7. Client behavior

(Implementation details in `react-dashboard` section 5; the rules below are the contract.)

- Build the URL from `window.location` (`wss:` on https). Offer subprotocol `monitor.v1`.
- Validate each message with Zod. Invalid messages are dropped and counted; more than N invalid messages in a window triggers a reconnect and a diagnostic.
- **Backoff**: exponential with full jitter, base 1 s, cap 30 s, reset after a connection stays healthy for 30 s. 1013 uses a base of 10 s. Never retry on fatal codes (1008, 4400, 4401).
- **Stale detection**: if no message arrives within `2 x interval_ms` (from `hello`) plus small margin, mark stale; after `4 x interval_ms`, close and reconnect.
- On `seq` gap: mark the gap in history; no resync of current state is needed (full snapshots).
- On reconnect: fetch `GET /api/v1/snapshot` once to fill the screen immediately while the socket reconnects, then continue from the stream.
- Tab hidden: optionally close after a configurable idle time and reconnect on `visibilitychange`; never poll from background tabs.
- Clean up on unmount: close the socket, clear timers, remove listeners. No orphan reconnect loops (important in React strict mode, which mounts twice in development).
- Expose `connectionState`, `lastMessageAt`, `droppedCount` and `invalidCount` to the UI for the stale/disconnected banners defined in `ui-design-system`.

## 8. Performance, compression and capacity

- **Message budget**: measure the serialized snapshot size in tests and fail CI above a configured budget (starting point: under 16 KiB with default top-N processes). Reduce by limiting processes, rounding floats (e.g. 1-2 decimals), short stable keys, and omitting unsubscribed groups, before reaching for compression.
- **Compression** (`permessage-deflate`): at 1 Hz and a few KiB per message, bandwidth is not the bottleneck, while per-connection compression state costs memory and CPU. **Default: disabled** (uvicorn `--ws-per-message-deflate false`); enable only if measurements on a remote/WAN deployment justify it, and re-measure CPU and RSS with 100 clients.
- **Uvicorn settings to set explicitly**: `--ws-max-size` (inbound limit, small, e.g. 4096; the default is far larger), `--ws-ping-interval`, `--ws-ping-timeout`, `--limit-concurrency`, `--timeout-keep-alive`, a single worker (see `python-backend`).
- **Fan-out cost** is O(clients) string sends per interval; target 100+ clients at 1 Hz with under 5 % extra CPU and flat memory. Measure, do not assume.
- **Rate**: default interval 1 s; clients may request 1 s to 10 s (never faster) through a validated `subscribe` option; `hello` advertises `min_interval_ms` and `max_interval_ms`. Changing defaults or limits needs approval.
- **Memory per client**: queue (small) + socket buffers; verify linear, bounded growth in a soak test.
- Use the monotonic clock for intervals and timeouts; wall clock only for `ts` display.

## 9. Reverse proxy and deployment

- The proxy must forward the upgrade: `proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";` (nginx) and raise `proxy_read_timeout` above the heartbeat window (default 60 s will cut quiet sockets).
- Disable proxy buffering for the WebSocket location; forward `Origin` and `Host` unchanged so origin checks work.
- Load balancers: idle timeouts (often 60 s) must exceed the longest silence; since snapshots flow every second this holds, but confirm for 0.5 Hz settings.
- Run **one app instance** by default. Multiple instances mean multiple samplers and different views; scaling out (Redis pub/sub, sticky sessions) requires approval and a design note.
- Container and systemd: non-root, file-descriptor limit raised to cover max clients plus headroom (`LimitNOFILE`).
- Observability: expose server metrics (connected clients, messages sent, dropped, send timeouts, rate-limit closes, handshake failures, close codes histogram) through the app's own metrics, never as fabricated values.

## 10. Testing strategy

| Layer | What to test | How |
|-------|--------------|-----|
| Contract | Every fixture validates against Pydantic **and** JSON Schema (server) and Zod (client); schema file unchanged unless approved | `tests/contract/`, frontend `test/contract/` |
| Unit (protocol) | Envelope validation, unknown type rejection, version mismatch, size limits, token bucket, backoff math | Pure pytest / Vitest with injectable clock and RNG |
| Hub | Drop-oldest, drop counters, publish never blocks, disconnect removes client, copy-on-iterate safety | pytest-asyncio with fake sockets |
| Endpoint | Origin rejection before accept, hello first, monotonic `seq`, subscribe validation, oversize close 1009, rate-limit close 4429, subprotocol negotiation | Starlette `TestClient.websocket_connect` |
| Slow-client isolation | A stalled client does not delay a fast one; its memory stays bounded; it is closed after the send timeout | Async test with a fake socket that never drains |
| Lifecycle | Shutdown sends `bye`, closes with 1001, cancels all tasks; connect/disconnect cycles return task and socket counts to baseline | Lifespan tests, `asyncio.all_tasks()` count |
| Client | Reconnect timing and jitter, no retry on fatal codes, stale detection, seq gap handling, unmount cleanup, strict-mode double mount | Vitest fake timers + fake `WebSocket` |
| Chaos | Network drop mid-stream, half-open connection (peer silent), server restart, proxy idle timeout | Integration with a toxic proxy or scripted socket drop; assert UI shows stale then recovers |
| Load and soak | 100-200 clients at 1 Hz for 1 hour: latency, CPU, RSS, task count, drops | Asyncio script using the `websockets` client, or Locust |
| Security | Bad origin, missing/expired token, token not logged, oversize frames, malformed JSON flood | Integration tests |

Tooling: `pytest`, `pytest-asyncio`, `httpx`, `websockets` (client, dev only), `pytest-cov`, `locust` (optional), Vitest, Playwright. Coverage floors: **95 %** on protocol, hub and client socket code.

Fixtures are real recorded or hand-written examples that match the schema; they live under `contracts/` or `test/`, never in production code.

## 11. Common pitfalls

- Per-client collection or serialization inside the connection handler.
- Unbounded per-client queue, or `await send` inside the broadcast loop.
- Mutating the client set while iterating over it.
- Accepting the socket before checking origin or token.
- Assuming the server notices a dead peer; no stale detection on the client.
- Reconnect without backoff or jitter, so a restart triggers a stampede.
- Retrying forever on auth, origin or version errors.
- Sending deltas without a resync path, then showing corrupted state after one drop.
- Showing the last-known value as if it were current when the stream stalled.
- Proxy idle timeout shorter than the quiet period; missing `Upgrade` headers.
- Compression enabled by default, inflating memory per connection.
- Default `--ws-max-size` left huge on the server.
- Long-lived secrets in query strings, or tokens appearing in access logs.
- Changing a field name on one side only.
- Client reconnect loops leaking after component unmount (especially in React strict mode).
- Socket.IO client against a plain WebSocket server (or vice versa).
- "Connection pooling" for WebSockets: each client needs one long-lived connection; multiplex groups inside it with `subscribe`.

## 12. Definition of done

- [ ] `contracts/ws/v1/` exists with schemas and fixtures; server and client tests both validate the same fixtures; CI blocks unapproved schema drift.
- [ ] Protocol documented: envelope, all message types, delivery semantics, state machine, close codes.
- [ ] Hub bounded and non-blocking; slow-client isolation test passes; drop counters surfaced in `meta` and server metrics.
- [ ] All limits implemented, configurable and tested: clients, per-IP, message size, rate, handshake, send timeout.
- [ ] Origin check (and auth if enabled) happens before `accept`; tokens never logged.
- [ ] Client: jittered backoff, fatal-code handling, stale detection, seq-gap handling, cleanup on unmount, all tested.
- [ ] Graceful shutdown sends `bye` and 1001; reconnect stampede avoided via client jitter; tested.
- [ ] Chaos tests (drop, half-open, restart, proxy timeout) demonstrate stale then recovery without manual refresh.
- [ ] Soak test (100+ clients, 1 h): flat memory, stable task and socket counts, CPU within budget; results recorded.
- [ ] Message-size budget enforced in CI; compression decision documented with measurements.
- [ ] Proxy configuration documented and verified (upgrade headers, timeouts, no buffering).
- [ ] Any contract, limit or default change approved.

## 13. Dependencies

**Server:** `fastapi`, `uvicorn[standard]`, `pydantic` (v2)

**Client:** native `WebSocket`, `zod`

**Dev and test:** `pytest`, `pytest-asyncio`, `httpx`, `websockets` (test and load client only), `pytest-cov`, `locust` (optional), `vitest`, `@playwright/test`, `jsonschema` (validate fixtures against generated schema)

**Not used:** Socket.IO, `aiohttp`, `requests`, any "websocket client wrapper" package, per-message encryption libraries.

## 14. Operations requiring user approval

Ask before:

- Adding, renaming or removing any message type, field or close code, or bumping the protocol version.
- Switching from full snapshots to deltas, batching, or priority classes.
- Enabling or changing authentication and token handling.
- Changing default limits (clients, rates, sizes, intervals, timeouts) or enabling compression.
- Scaling beyond a single instance (multi-worker, Redis fan-out, sticky sessions).
- Adding any new dependency, or a different WebSocket framework or library.
- Relaxing the origin check or exposing the endpoint beyond localhost.

After an approved change: update `contracts/ws/v1/`, regenerate schemas, update fixtures, and sync `python-backend` section 6 and `react-dashboard` section 5.