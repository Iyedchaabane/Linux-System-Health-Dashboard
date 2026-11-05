import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { act, render, screen } from "@testing-library/react";
import hello from "../../../contracts/ws/v1/fixtures/hello.json";

import { useDashboardStore } from "../../src/application/store";
import { connectDashboard, type DashboardConnection } from "../../src/application/connect";
import { ProcessPanel } from "../../src/presentation/components/ProcessPanel";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  binaryType = "blob";
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly url: string, readonly protocol: string) {
    FakeWebSocket.instances.push(this);
  }

  open() { this.onopen?.(); }
  message(payload: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
  }
  close = vi.fn((code = 1000) => {
    this.onclose?.(new CloseEvent("close", { code }));
  });
}

function groups(cpu: number) {
  return { cpu: { status: "ok" as const, value: { cpu_total: cpu }, partial: false } };
}

function snapshot(seq: number, cpu: number) {
  return {
    v: 1,
    type: "snapshot",
    seq,
    ts: seq,
    data: { type: "snapshot", groups: groups(cpu), meta: null },
  };
}

function deferred() {
  let resolve!: (value: unknown) => void;
  const promise = new Promise<unknown>((done) => { resolve = done; });
  return { promise, resolve };
}

const state = () => useDashboardStore.getState();

describe("connectDashboard reconnect epochs", () => {
  let connection: DashboardConnection | undefined;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(10_000);
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    state().reset();
  });

  afterEach(() => {
    connection?.dispose();
    connection = undefined;
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function start(fetchSnapshot?: () => Promise<unknown>) {
    connection = connectDashboard({ socketUrl: "ws://localhost/ws/v1/metrics", fetchSnapshot });
    const socket = FakeWebSocket.instances[FakeWebSocket.instances.length - 1]!;
    socket.open();
    socket.message(hello);
    return socket;
  }

  function reconnect(socket: FakeWebSocket) {
    socket.close(1001);
    expect(state().connectionState).toBe("disconnected");
    vi.advanceTimersToNextTimer();
    const next = FakeWebSocket.instances[FakeWebSocket.instances.length - 1]!;
    expect(next).not.toBe(socket);
    next.open();
    next.message(hello);
    return next;
  }

  it("progresses from loading through hello to the first live snapshot without initial REST", () => {
    const fetchSnapshot = vi.fn();
    connection = connectDashboard({ socketUrl: "ws://localhost/ws/v1/metrics", fetchSnapshot });
    const socket = FakeWebSocket.instances[0]!;
    expect(state().connectionState).toBe("connecting");
    expect(state().metricStates.cpu.status).toBe("loading");
    expect(socket.protocol).toBe("monitor.v1");
    socket.open();
    expect(state().connectionState).toBe("connecting");
    socket.message({ ...hello, data: { ...hello.data, interval_ms: 250 } });
    expect(state().intervalMs).toBe(250);
    expect(state().latestSnapshot).toBeNull();
    expect(state().connectionState).toBe("connecting");
    socket.message(snapshot(1, 12));
    expect(state().connectionState).toBe("open");
    expect(state().metricStates.cpu).toEqual({ status: "ok", value: { cpu_total: 12 } });
    expect(state().latestSnapshot?.seq).toBe(1);
    expect(fetchSnapshot).not.toHaveBeenCalled();
  });

  it("accepts sequence 1 after sequence 100 on a new epoch but does not make retained data live on hello", () => {
    const socket = start();
    socket.message(snapshot(100, 90));
    const next = reconnect(socket);
    expect(state().connectionState).toBe("connecting");
    expect(state().metricStates.cpu).toEqual({ status: "ok", value: { cpu_total: 90 } });
    expect(state().maxSeqSeen).toBe(-1);
    next.message(snapshot(1, 15));
    expect(state().latestSnapshot?.seq).toBe(1);
    expect(state().metricStates.cpu).toEqual({ status: "ok", value: { cpu_total: 15 } });
    expect(state().connectionState).toBe("open");
    expect(state().seqGaps).toEqual([]);
    expect(state().cpuHistory).toEqual([90, 15]);
  });

  it("rejects duplicate and out-of-order snapshots within the same epoch", () => {
    const socket = start();
    socket.message(snapshot(5, 15));
    const before = state();
    socket.message(snapshot(5, 80));
    socket.message(snapshot(4, 90));
    expect(state()).toBe(before);
    socket.message(snapshot(6, 20));
    expect(state().cpuHistory).toEqual([15, 20]);
    expect(state().latestSnapshot?.seq).toBe(6);
  });

  it("ignores captured callbacks from an old socket after the new socket has fresh data", () => {
    const socket = start();
    socket.message(snapshot(100, 90));
    const old = { open: socket.onopen!, message: socket.onmessage!, close: socket.onclose!, error: socket.onerror! };
    const next = reconnect(socket);
    next.message(snapshot(1, 15));
    const before = state();
    old.open();
    old.message(new MessageEvent("message", { data: JSON.stringify(snapshot(101, 99)) }));
    old.message(new MessageEvent("message", { data: "invalid" }));
    old.close(new CloseEvent("close", { code: 1008 }));
    old.error();
    expect(state()).toBe(before);
    expect(FakeWebSocket.instances).toHaveLength(2);
    // The original epoch's stale deadline must not close or mark the new one stale.
    vi.advanceTimersByTime(1500);
    expect(state().connectionState).toBe("open");
    expect(next.close).not.toHaveBeenCalled();
  });

  it.each([undefined, null, { dropped_since_last: 2 }])("accepts actual REST shape with meta %j and no synthetic WS sequence or live status", async (meta) => {
    const rest = deferred();
    const fetchSnapshot = vi.fn(() => rest.promise);
    const socket = start(fetchSnapshot);
    socket.message(snapshot(100, 90));
    const next = reconnect(socket);
    const messageTime = state().lastMessageAt;
    rest.resolve({ ts: 200, groups: groups(25), ...(meta === undefined ? {} : { meta }) });
    await rest.promise;
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    expect(state().latestSnapshot).toEqual({ ts: 200, groups: groups(25), seq: null });
    expect(state().metricStates.cpu).toEqual({ status: "ok", value: { cpu_total: 25 } });
    expect(state().connectionState).toBe("connecting");
    expect(state().maxSeqSeen).toBe(-1);
    expect(state().lastMessageAt).toBe(messageTime);
    expect(state().seqGaps).toEqual([]);
    next.message(snapshot(1, 30));
    expect(state().maxSeqSeen).toBe(1);
    expect(state().cpuHistory).toEqual([90, 25, 30]);
    expect(state().connectionState).toBe("open");
  });

  it("ignores delayed REST once a newer WS snapshot has arrived", async () => {
    const rest = deferred();
    const socket = start(() => rest.promise);
    socket.message(snapshot(100, 90));
    const next = reconnect(socket);
    next.message(snapshot(1, 15));
    const before = state();
    rest.resolve({ ts: 200, groups: groups(99) });
    await rest.promise;
    expect(state()).toBe(before);
    expect(state().cpuHistory).toEqual([90, 15]);
  });

  it.each(["same", "older"] as const)("removes REST process rows on WS unavailable and rejects delayed %s-epoch REST", async (epoch) => {
    const first = deferred();
    const delayed = deferred();
    const third = deferred();
    const fetchSnapshot = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(delayed.promise)
      .mockReturnValueOnce(third.promise);
    const socket = start(fetchSnapshot);
    // Start without a processes group, as on servers before process support.
    socket.message(snapshot(100, 90));
    expect(state().latestSnapshot?.groups.processes).toBeUndefined();
    const next = reconnect(socket);
    const available = {
      status: "ok", partial: false,
      value: { items: [
        { pid: 71, name: "old-worker", cpu_percent: null, memory_rss_bytes: 1024 },
        { pid: 72, name: "old-helper", cpu_percent: 2, memory_rss_bytes: 2048 },
      ], skipped: 0 },
    };
    first.resolve({ ts: 200, groups: { processes: available } });
    await first.promise;
    expect(state().latestSnapshot?.seq).toBeNull();
    expect(state().metricStates.processes).toEqual({ status: "ok", value: available.value });
    render(createElement(ProcessPanel));
    expect(screen.getByRole("rowheader", { name: "old-worker" })).toBeTruthy();
    expect(screen.getByRole("rowheader", { name: "old-helper" })).toBeTruthy();

    let current!: FakeWebSocket;
    act(() => {
      current = reconnect(next); // A distinct, still-pending REST recovery.
      if (epoch === "older") current = reconnect(current);
    });
    const unavailable = {
      status: "unavailable", kind: "permission", reason: "Process listing is no longer permitted",
    };
    act(() => current.message({
      v: 1, type: "snapshot", seq: 1, ts: 201,
      data: { type: "snapshot", groups: { processes: unavailable }, meta: null },
    }));
    expect(state().connectionState).toBe("open");
    expect(state().metricStates.processes).toEqual(unavailable);
    expect(state().metricStates.processes).not.toHaveProperty("value");
    expect(state().metricStates.processes).not.toHaveProperty("items");
    expect(state().latestSnapshot?.groups.processes).toEqual(unavailable);
    expect(screen.getByText(unavailable.reason)).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryAllByRole("rowheader")).toHaveLength(0);
    expect(screen.queryByText("old-worker")).toBeNull();
    expect(screen.queryByText("old-helper")).toBeNull();

    const before = state();
    await act(async () => {
      delayed.resolve({ ts: 202, groups: { processes: available } });
      await delayed.promise;
    });
    expect(fetchSnapshot).toHaveBeenCalledTimes(epoch === "same" ? 2 : 3);
    expect(state()).toBe(before);
    expect(screen.getByText(unavailable.reason)).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByText("old-worker")).toBeNull();
    expect(screen.queryByText("old-helper")).toBeNull();
  });

  it("ignores REST from an older epoch even before the next epoch receives a snapshot", async () => {
    const first = deferred();
    const second = deferred();
    const fetchSnapshot = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const socket = start(fetchSnapshot);
    socket.message(snapshot(100, 90));
    const next = reconnect(socket);
    reconnect(next);
    const before = state();
    first.resolve({ ts: 200, groups: groups(99) });
    await first.promise;
    expect(state()).toBe(before);
    second.resolve({ ts: 201, groups: groups(25) });
    await second.promise;
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
    expect(state().metricStates.cpu).toEqual({ status: "ok", value: { cpu_total: 25 } });
    expect(state().connectionState).toBe("connecting");
  });

  it.each(["closed", "disposed"])("ignores pending recovery after its socket is %s", async (ending) => {
    const rest = deferred();
    const socket = start(() => rest.promise);
    socket.message(snapshot(100, 90));
    const next = reconnect(socket);
    if (ending === "closed") next.close(1001);
    else connection!.dispose();
    const before = state();
    rest.resolve({ ts: 200, groups: groups(99) });
    await rest.promise;
    expect(state()).toBe(before);
    connection!.dispose();
    vi.advanceTimersByTime(60_000);
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("keeps stale recovery non-live until a fresh WS snapshot and clears timers on dispose", async () => {
    const rest = deferred();
    const socket = start(() => rest.promise);
    socket.message(snapshot(100, 90));
    vi.advanceTimersByTime(2000);
    expect(state().connectionState).toBe("stale");
    vi.advanceTimersByTime(2000);
    expect(state().connectionState).toBe("disconnected");
    vi.advanceTimersToNextTimer();
    const next = FakeWebSocket.instances[FakeWebSocket.instances.length - 1]!;
    next.open();
    next.message(hello);
    vi.advanceTimersByTime(2000);
    expect(state().connectionState).toBe("stale");
    rest.resolve({ ts: 200, groups: groups(25) });
    await rest.promise;
    expect(state().connectionState).toBe("stale");
    expect(state().metricStates.cpu).toEqual({ status: "ok", value: { cpu_total: 25 } });
    next.message(snapshot(1, 15));
    expect(state().connectionState).toBe("open");
    expect(state().cpuHistory).toEqual([90, 25, 15]);
    connection!.dispose();
    vi.advanceTimersByTime(60_000);
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(vi.getTimerCount()).toBe(0);
  });
});
