import { describe, expect, it } from "vitest";

import { parseServerMessage } from "../../src/infrastructure/ws/schemas";

function snapshotWith(processes: unknown) {
  return {
    v: 1,
    type: "snapshot",
    seq: 1,
    ts: 1,
    data: { type: "snapshot", groups: { processes } },
  };
}

function row(overrides: Record<string, unknown> = {}) {
  return {
    pid: 1234,
    name: "worker",
    cpu_percent: 12.5,
    memory_rss_bytes: 1024,
    ...overrides,
  };
}

describe("processes group schema", () => {
  it("accepts an ok payload and keeps a null CPU measurement null", () => {
    const parsed = parseServerMessage(
      snapshotWith({
        status: "ok",
        partial: false,
        value: {
          items: [row({ cpu_percent: null }), row({ pid: 7, cpu_percent: 250 })],
          skipped: 0,
          total: 2,
        },
      }),
    );
    const groups = (parsed.data as { groups: Record<string, unknown> }).groups;
    const value = groups.processes as {
      value: { items: Array<{ cpu_percent: number | null }> };
    };
    expect(value.value.items[0]?.cpu_percent).toBeNull();
    expect(value.value.items[1]?.cpu_percent).toBe(250);
  });

  it("accepts a partial payload with skipped processes", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: true,
          value: { items: [row()], skipped: 3, total: 10 },
        }),
      ),
    ).not.toThrow();
  });

  it.each([
    ["equal to the item count", 2],
    ["greater than the item count", 25],
  ])("accepts a total %s", (_label, total) => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { items: [row(), row({ pid: 7 })], skipped: 0, total },
        }),
      ),
    ).not.toThrow();
  });

  it("accepts an unavailable payload", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "unavailable",
          kind: "permission",
          reason: "Process listing is not permitted",
        }),
      ),
    ).not.toThrow();
  });

  it("accepts snapshots that omit the optional processes group", () => {
    expect(() =>
      parseServerMessage({
        v: 1,
        type: "snapshot",
        seq: 1,
        ts: 1,
        data: {
          type: "snapshot",
          groups: {
            cpu: { status: "ok", value: { cpu_total: 10 }, partial: false },
          },
        },
      }),
    ).not.toThrow();
  });

  it.each([
    ["zero pid", row({ pid: 0 })],
    ["negative pid", row({ pid: -1 })],
    ["fractional pid", row({ pid: 1.5 })],
    ["129-character name", row({ name: "x".repeat(129) })],
    ["129 non-BMP code points", row({ name: "😀".repeat(129) })],
    ["129 mixed code points", row({ name: "x".repeat(64) + "😀".repeat(65) })],
    ["129 code points in combining sequences", row({ name: "e\u0301".repeat(64) + "e" })],
    ["negative RSS", row({ memory_rss_bytes: -1 })],
    ["fractional RSS", row({ memory_rss_bytes: 1.5 })],
    ["negative CPU", row({ cpu_percent: -0.1 })],
    ["infinite CPU", row({ cpu_percent: Infinity })],
    ["NaN CPU", row({ cpu_percent: Number.NaN })],
  ])("rejects an invalid row: %s", (_label, invalidRow) => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { items: [invalidRow], skipped: 0, total: 1 },
        }),
      ),
    ).toThrow();
  });

  it.each([
    ["missing pid", { name: "worker", cpu_percent: 1, memory_rss_bytes: 1024 }],
    ["missing name", { pid: 1234, cpu_percent: 1, memory_rss_bytes: 1024 }],
    ["missing CPU", { pid: 1234, name: "worker", memory_rss_bytes: 1024 }],
    ["missing RSS", { pid: 1234, name: "worker", cpu_percent: 1 }],
  ])("rejects a row with %s", (_label, incompleteRow) => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { items: [incompleteRow], skipped: 0, total: 1 },
        }),
      ),
    ).toThrow();
  });

  it.each([
    ["empty", ""],
    ["128 ASCII code points", "x".repeat(128)],
    ["128 non-BMP code points", "😀".repeat(128)],
    ["128 mixed code points", "x".repeat(64) + "😀".repeat(64)],
    ["128 code points in 64 combining sequences", "e\u0301".repeat(64)],
    ["whitespace and decomposed text", "  e\u0301 😀  "],
  ])("accepts and preserves %s names through a JSON snapshot", (_label, name) => {
    const message = snapshotWith({
      status: "ok",
      partial: false,
      value: { items: [row({ name })], skipped: 0, total: 1 },
    });
    const parsed = parseServerMessage(JSON.parse(JSON.stringify(message)));
    expect(parsed).toEqual(message);
  });

  it("rejects an ok payload missing partial", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          value: { items: [row()], skipped: 0, total: 1 },
        }),
      ),
    ).toThrow();
  });

  it("rejects an ok payload missing skipped", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { items: [row()], total: 1 },
        }),
      ),
    ).toThrow();
  });

  it("rejects an ok payload missing total", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { items: [row()], skipped: 0 },
        }),
      ),
    ).toThrow();
  });

  it("rejects an ok payload missing items", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { skipped: 0, total: 0 },
        }),
      ),
    ).toThrow();
  });

  it.each([
    ["negative", -1],
    ["fractional", 1.5],
    ["boolean", true],
  ])("rejects a %s total", (_label, total) => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { items: [row()], skipped: 0, total },
        }),
      ),
    ).toThrow();
  });

  it("rejects a total below the reported item count", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { items: [row(), row({ pid: 7 })], skipped: 0, total: 1 },
        }),
      ),
    ).toThrow();
  });

  it("rejects unknown fields on a process row", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: {
            items: [row({ command: "worker --serve" })],
            skipped: 0,
            total: 1,
          },
        }),
      ),
    ).toThrow();
  });

  it("rejects unknown fields on the process list value", () => {
    expect(() =>
      parseServerMessage(
        snapshotWith({
          status: "ok",
          partial: false,
          value: { items: [row()], skipped: 0, total: 1, command: "worker" },
        }),
      ),
    ).toThrow();
  });
});
