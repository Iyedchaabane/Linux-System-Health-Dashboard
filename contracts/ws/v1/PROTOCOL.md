# WebSocket Protocol v1

## Overview

Real-time metric snapshots between the Linux System Health Dashboard backend
(FastAPI/uvicorn) and browser clients (React). One endpoint: `/ws/v1/metrics`.
Subprotocol: `monitor.v1`.

## Version and envelope

Every message, both directions:

```json
{ "v": 1, "type": "snapshot", "seq": 1042, "ts": 1767225600, "data": { } }
```

- `v` (int): protocol version, always `1`. Mismatch is a hard error (close 4400).
- `type` (string): allowlisted per direction.
- `seq` (int): server messages only; starts at 0 per connection, increments by 1
  per attempted message; gaps mean drops.
- `ts` (int): server Unix epoch milliseconds at the API/WebSocket boundary;
  display only.
- `data`: type-specific payload; `extra="forbid"` server-side.

## Message types

Server → client: `hello`, `snapshot`, `error`, `ping`, `bye`.
Client → server: `subscribe`, `pong`, `ping`.

### `hello`
```json
{
  "v": 1,
  "type": "hello",
  "seq": 0,
  "ts": 1767225600512,
  "data": {
    "interval_ms": 1000,
    "max_message_bytes": 16384,
    "groups": ["cpu", "memory"],
    "server_time": 1767225600.512,
    "limits": {
      "max_clients": 100,
      "max_clients_per_ip": 10,
      "max_message_bytes": 4096,
      "rate_limit_burst": 10,
      "rate_limit_refill_per_second": 2.0,
      "send_timeout_seconds": 5.0,
      "handshake_timeout_seconds": 5.0
    }
  }
}
```

### `snapshot`
```json
{
  "v": 1,
  "type": "snapshot",
  "seq": 2,
  "ts": 1767225602500,
  "data": {
    "groups": {
      "cpu": { "status": "ok", "value": { "cpu_total": 12.5 }, "partial": false },
      "memory": { "status": "ok", "value": { "total": 1 }, "partial": false }
    },
    "meta": { "dropped_since_last": 0 }
  }
}
```

Group states: `ok` (`value`, optional `partial`) or `unavailable`
(`kind`, `reason`). Defaults: subscribed to implemented groups until told
otherwise.

### `error`
```json
{ "v": 1, "type": "error", "seq": 3, "ts": 1767225603500, "data": { "code": "RATE_LIMIT_EXCEEDED", "message": "safe text" } }
```

### `ping` / `pong` / `bye`
- Server `ping`: liveness probe (data: minimal).
- Client `pong`: reply to ping.
- Client `ping`: liveness probe (server replies `pong`).
- `bye`: orderly close notice; data `{ "reason": "shutdown" }`.

## Delivery semantics
- At-most-once, full snapshots, latest-wins, per-connection ordered.
- Server never replays backlog over socket; gaps handled via history REST.

## Close codes
`1000` normal, `1001` going away, `1008` policy violation, `1009` message too big,
`1011` internal error, `1013` try again later, `4400` version/invalid, `4401` auth
(deferred), `4429` rate limit exceeded.

## Limits
max clients 100, per IP 10, inbound message 4096 B, rate burst 10/refill 2/s,
handshake 5 s, send timeout 5 s, stale at 2x interval, send timeout on drop.
