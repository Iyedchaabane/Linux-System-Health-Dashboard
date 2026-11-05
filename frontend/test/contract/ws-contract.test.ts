import { describe, expect, it } from "vitest";

import { parseServerMessage } from "../../src/infrastructure/ws/schemas";

const fixtures = {
  "bye.json": { v: 1, type: "bye", seq: 8, ts: 1767225608500, data: { reason: "shutdown" } },
  "error_invalid_message.json": {
    v: 1,
    type: "error",
    seq: 3,
    ts: 1767225603500,
    data: { code: "INVALID_MESSAGE", message: "safe validation error text" },
  },
  "hello.json": {
    v: 1,
    type: "hello",
    seq: 0,
    ts: 1767225600512,
    data: {
      interval_ms: 1000,
      max_message_bytes: 16384,
      groups: ["cpu", "memory"],
      server_time: 1767225600.512,
      limits: {
        max_clients: 100,
        max_clients_per_ip: 10,
        max_message_bytes: 4096,
        rate_limit_burst: 10,
        rate_limit_refill_per_second: 2.0,
        send_timeout_seconds: 5.0,
        handshake_timeout_seconds: 5.0,
      },
    },
  },
  "snapshot_ok.json": {
    v: 1,
    type: "snapshot",
    seq: 2,
    ts: 1767225602500,
    data: {
      type: "snapshot",
      groups: {
        cpu: { status: "ok", value: { cpu_total: 12.5 }, partial: false },
        memory: { status: "ok", value: { total: 1, available: 2, used_percent: 50 }, partial: false },
      },
      meta: { dropped_since_last: 0 },
    },
  },
  "snapshot_partial.json": {
    v: 1,
    type: "snapshot",
    seq: 4,
    ts: 1767225604500,
    data: {
      type: "snapshot",
      groups: { cpu: { status: "ok", value: { cpu_total: 12.5 }, partial: true } },
    },
  },
  "snapshot_unavailable.json": {
    v: 1,
    type: "snapshot",
    seq: 6,
    ts: 1767225606500,
    data: {
      type: "snapshot",
      groups: {
        cpu: { status: "unavailable", kind: "permission", reason: "proc access denied" },
        memory: { status: "ok", value: { total: 1, available: 2, used_percent: 50 }, partial: false },
      },
    },
  },
} as const;

describe("WS contract fixtures (server -> client)", () => {
  for (const [name, fixture] of Object.entries(fixtures)) {
    it(`parses ${name}`, () => {
      const msg = parseServerMessage(fixture);
      expect(msg.v).toBe(1);
    });
  }
});

describe("invalid payloads", () => {
  it("rejects missing v", () => {
    expect(() =>
      parseServerMessage({ type: "ping", seq: 0, ts: 1, data: { type: "ping" } }),
    ).toThrow();
  });
  it("rejects unsupported message type", () => {
    expect(() =>
      parseServerMessage({ v: 1, type: "unknown", seq: 0, ts: 1, data: {} }),
    ).toThrow();
  });
  it("rejects hello data missing limits", () => {
    expect(() =>
      parseServerMessage({
        v: 1,
        type: "hello",
        seq: 0,
        ts: 1,
        data: { type: "hello", interval_ms: 1000, max_message_bytes: 1, groups: [], server_time: 1 },
      }),
    ).toThrow();
  });
  it("rejects snapshot group value that is not an object", () => {
    expect(() =>
      parseServerMessage({
        v: 1,
        type: "snapshot",
        seq: 1,
        ts: 1,
        data: { type: "snapshot", groups: { cpu: { status: "ok", value: 123, partial: false } } },
      }),
    ).toThrow();
  });
  it("rejects negative ts", () => {
    expect(() =>
      parseServerMessage({ v: 1, type: "ping", seq: 0, ts: -1, data: { type: "ping" } }),
    ).toThrow();
  });
});


describe("WS contract: disk and network", () => {
  it("parses a snapshot containing disk and network groups", () => {
    const raw = {
      v: 1,
      type: "snapshot",
      seq: 10,
      ts: 1767225610000,
      data: {
        type: "snapshot",
        groups: {
          disk: { status: "ok", value: { device: "/", total: 100, used: 40, percent: 40 }, partial: false },
          network: { status: "ok", value: { rx_bytes: 1000, tx_bytes: 500 }, partial: false },
        },
      },
    };
    const msg = parseServerMessage(raw);
    expect(msg.type).toBe("snapshot");
    const snap = msg.data as { groups: Record<string, { status: string }> };
    expect(snap.groups.disk.status).toBe("ok");
    expect(snap.groups.network.status).toBe("ok");
  });

  it("accepts unavailable disk and network states", () => {
    const raw = {
      v: 1,
      type: "snapshot",
      seq: 11,
      ts: 1767225611000,
      data: {
        type: "snapshot",
        groups: {
          disk: { status: "unavailable", kind: "permission", reason: "access denied" },
          network: { status: "unavailable", kind: "transient", reason: "timeout" },
        },
      },
    };
    expect(() => parseServerMessage(raw)).not.toThrow();
  });
});
