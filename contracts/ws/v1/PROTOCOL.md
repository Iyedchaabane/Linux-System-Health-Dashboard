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
    "groups": ["cpu", "memory", "processes"],
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
    "type": "snapshot",
    "groups": {
      "cpu": { "status": "ok", "value": { "cpu_total": 12.5 }, "partial": false },
      "memory": { "status": "ok", "value": { "total": 1 }, "partial": false }
    },
    "meta": { "dropped_since_last": 0 }
  }
}
```

Every snapshot payload carries a `type` discriminator inside `data` whose only
valid value is `snapshot`; the published schema requires it. `meta` is always
present as an object, and `meta.dropped_since_last` is always an integer on the
wire: `null` is not a valid snapshot `meta`.

Group states: `ok` (`value`, optional `partial`) or `unavailable`
(`kind`, `reason`). Defaults: subscribed to implemented groups until told
otherwise.

#### Optional `processes` group (approved T2 contract)

The additive `groups.processes` shape is shared by REST `/api/v1/snapshot`
and WebSocket `snapshot.data.groups`; v1 is unchanged. It may be absent.
The `hello` message advertises `processes` alongside `cpu` and `memory`;
this is an additive entry in the existing capability list and does not
change the protocol version.

An available group is `{status: "ok", partial: boolean, value: {items:
ProcessRow[], skipped: integer, total: integer}}`. Each row contains only:

- `pid`: positive integer.
- `name`: string of at most 128 characters, safely truncated by the collector.
- `cpu_percent`: finite nonnegative number or `null`; 100 means one logical
  CPU, so values above 100 are valid. Null means measuring: insufficient
  consecutive samples for this process identity, including after PID reuse.
- `memory_rss_bytes`: nonnegative integer, resident memory in bytes.

`skipped` is a nonnegative integer counting skipped processes. `partial` is
true when processes were skipped or CPU measurements are incomplete. Top-N
truncation alone is not partial.

`total` is a nonnegative integer: the number of readable, identity-checked
processes in the same sample before top-N truncation. It excludes `skipped`
processes and always satisfies `total >= len(items)`. `total` greater than
`len(items)` reports truncation. It is not a host-wide inventory and does not
reflect a cgroup process limit. Items are ordered by CPU descending, null last,
with PID ascending for ties. Only namespace-visible processes are covered:
neither a complete host-wide view nor host-wide totals are implied.
Unavailable groups reuse the existing `status`, `kind`, `reason` shape.
No command lines, usernames, environment variables, or other sensitive fields
are included. No process history is retained.

The stream uses the existing configured cap (default **25**, existing upper
bound **100** unchanged); REST snapshots serve that same list, not a separate
process endpoint. The snapshot budget remains **16 KiB**. Ordering, partial
semantics, truncation and configured limits are collector integration duties;
the wire models validate field shapes and bounds, not collection behavior.

Schema maintenance currently uses the committed static JSON Schema; no schema
generation tool exists in this repository. The processes shape is also exposed
by the Pydantic models' JSON Schema for both REST and WebSocket snapshots. The
static schema can only require `total` to be a nonnegative integer; the
cross-field invariant `total >= len(items)` is enforced by the Pydantic wire
models and the domain entity.

#### Snapshot size budget and honest degradation

Outbound snapshot messages are compact UTF-8 JSON without ASCII escaping. The
budget is measured on the final encoded message, as UTF-8 bytes after `seq` and
`meta` are applied and excluding WebSocket framing, against the configured
snapshot budget (default **16,384 bytes**).

When a snapshot exceeds the budget, the server replaces whole groups with
`{"status": "unavailable", "kind": "transient", "reason": "..."}` in descending
encoded-size order (ties by group name) until the message fits, at most one
pass over the groups. It never truncates a list, alters or drops individual
rows, shortens process names, or fabricates values. Groups already
`unavailable` are not replaced. If the final encoded message still does not fit
after that single pass, it is never sent: the connection closes with **1011**
and a static internal-error reason, without an extra error or heartbeat frame.
Normal connection cleanup still runs, and pending drops are not acknowledged
as delivered. Terminal failures share a process-wide, thread-safe warning
throttle: the first warning is immediate, subsequent warnings are suppressed
for 60 monotonic seconds. These warnings contain only a static category, the
configured budget and final byte size, never group names or payload contents.

REST `GET /api/v1/snapshot` uses the same whole-group degradation policy, but
selects groups by measuring a canonical WebSocket-shaped message with `seq=1`
and `meta.dropped_since_last=0`, not the REST body. WebSocket degradation uses
the actual connection sequence and drop metadata, followed by a hard check of
the final encoded message bytes. Thus REST and WebSocket may report different
group availability near budget boundaries even for the same source snapshot
timestamp. Neither transport changes the cached source snapshot.

After REST group selection, the final normalized UTF-8 REST body is checked
against the budget for both Pydantic JSON and compact JSON serialization paths.
If that final check fails, REST fails closed without refitting groups. A terminal
budget failure at either REST check returns **503** in the existing canonical
error envelope, with code
`INTERNAL_ERROR`, message `Internal server error`, and the normal request ID.
Other unexpected errors retain their existing 500 behavior. This behavior reuses the
existing `unavailable` shape; it adds no message type, field, close code or
protocol version change, and the budget, top-N and name limits are unchanged.

### `error`
```json
{ "v": 1, "type": "error", "seq": 3, "ts": 1767225603500, "data": { "code": "RATE_LIMIT_EXCEEDED", "message": "safe text" } }
```

### `ping` / `pong` / `bye`
- Server `ping`: liveness probe; data is `{}` or `{ "type": "ping" }`.
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
