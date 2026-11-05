import { beforeEach, describe, expect, it } from "vitest";
import { useDashboardStore } from "../../src/application/store";

describe("dashboard store", () => {
  beforeEach(() => {
    useDashboardStore.getState().reset();
  });

  it("starts loading", () => {
    expect(useDashboardStore.getState().connectionState).toBe("connecting");
    expect(useDashboardStore.getState().metricStates.cpu.status).toBe("loading");
  });

  describe("setConnectionMeta", () => {
    it("updates intervalMs when provided", () => {
      useDashboardStore.getState().setConnectionMeta({ intervalMs: 2000 });
      expect(useDashboardStore.getState().intervalMs).toBe(2000);
    });
    it("leaves unchanged when not provided", () => {
      useDashboardStore.getState().setConnectionMeta({});
      expect(useDashboardStore.getState().intervalMs).toBe(1000);
    });
  });

  describe("setConnectionState", () => {
    it("connecting -> open", () => {
      useDashboardStore.getState().setConnectionState("open");
      expect(useDashboardStore.getState().connectionState).toBe("open");
    });
  });

  describe("ingestSnapshot", () => {
    it("sets latestSnapshot and updates lastMessageAt", () => {
      useDashboardStore.getState().ingestSnapshot({
        groups: { cpu: { status: "ok", value: { cpu_total: 1 } as never, partial: false } },
        seq: 5,
        ts: 100,
      });
      expect(useDashboardStore.getState().latestSnapshot?.seq).toBe(5);
      expect(useDashboardStore.getState().lastMessageAt).not.toBeNull();
      const cpu = useDashboardStore.getState().metricStates.cpu;
      expect(cpu.status).toBe("ok");
    });

    it("records seq gaps", () => {
      const s = useDashboardStore.getState();
      s.ingestSnapshot({ groups: {}, seq: 2, ts: 1 });
      s.ingestSnapshot({ groups: {}, seq: 5, ts: 2 });
      const gaps = useDashboardStore.getState().seqGaps;
      expect(gaps).toContain(3);
      expect(gaps).toContain(4);
    });

    it("does not fabricate gaps on sequential ingest", () => {
      const s = useDashboardStore.getState();
      s.ingestSnapshot({ groups: {}, seq: 1, ts: 1 });
      s.ingestSnapshot({ groups: {}, seq: 2, ts: 2 });
      expect(useDashboardStore.getState().seqGaps).toEqual([]);
    });
  });

  it("markStale transitions to stale", () => {
    useDashboardStore.getState().markStale();
    expect(useDashboardStore.getState().connectionState).toBe("stale");
  });

  it("markDisconnected transitions to disconnected/fatal", () => {
    useDashboardStore.getState().markDisconnected();
    expect(useDashboardStore.getState().connectionState).toBe("disconnected");
    useDashboardStore.getState().markDisconnected(true);
    expect(useDashboardStore.getState().connectionState).toBe("fatal");
  });

  it("reset clears all state", () => {
    const s = useDashboardStore.getState();
    s.ingestSnapshot({ groups: {}, seq: 7, ts: 1 });
    s.setConnectionState("open");
    s.reset();
    expect(s.lastMessageAt).toBeNull();
    expect(useDashboardStore.getState().maxSeqSeen).toBe(-1);
    expect(useDashboardStore.getState().connectionState).toBe("connecting");
  });

  it("reset clears every metric history", () => {
    useDashboardStore.getState().ingestSnapshot({
      groups: {
        cpu: { status: "ok", value: { cpu_total: 12 } as never, partial: false },
        memory: { status: "ok", value: { used_percent: 40 } as never, partial: false },
        disk: { status: "ok", value: { percent: 55 } as never, partial: false },
        network: { status: "ok", value: { rx_bytes: 4096 } as never, partial: false },
      },
      seq: 1,
      ts: 1,
    });
    const seeded = useDashboardStore.getState();
    expect(seeded.cpuHistory).toEqual([12]);
    expect(seeded.memoryHistory).toEqual([40]);
    expect(seeded.diskHistory).toEqual([55]);
    // A single counter sample cannot produce a rate: the history records the
    // gap rather than the cumulative total.
    expect(seeded.networkHistory).toEqual([null]);

    useDashboardStore.getState().reset();

    const reset = useDashboardStore.getState();
    expect(reset.cpuHistory).toEqual([]);
    expect(reset.memoryHistory).toEqual([]);
    expect(reset.diskHistory).toEqual([]);
    expect(reset.networkHistory).toEqual([]);
    expect(reset.latestSnapshot).toBeNull();
  });
});

describe("ingestSnapshot sequence guard", () => {
  it("rejects older snapshot", () => {
    const s = useDashboardStore.getState();
    s.ingestSnapshot({ groups: {}, seq: 5, ts: 100 });
    const before = useDashboardStore.getState().latestSnapshot;
    s.ingestSnapshot({ groups: {}, seq: 3, ts: 101 });
    expect(useDashboardStore.getState().latestSnapshot).toBe(before);
  });
  it("rejects duplicate seq", () => {
    const s = useDashboardStore.getState();
    s.ingestSnapshot({ groups: {}, seq: 5, ts: 100 });
    const before = useDashboardStore.getState().latestSnapshot;
    s.ingestSnapshot({ groups: {}, seq: 5, ts: 101 });
    expect(useDashboardStore.getState().latestSnapshot).toBe(before);
  });
  it("accepts newer snapshot after reject", () => {
    const s = useDashboardStore.getState();
    s.ingestSnapshot({ groups: {}, seq: 5, ts: 100 });
    s.ingestSnapshot({ groups: {}, seq: 3, ts: 101 });
    s.ingestSnapshot({ groups: {}, seq: 6, ts: 102 });
    expect(useDashboardStore.getState().latestSnapshot?.seq).toBe(6);
  });
  it("does not modify metric states on reject", () => {
    const s = useDashboardStore.getState();
    s.ingestSnapshot({
      groups: { cpu: { status: "ok", value: { cpu_total: 1 } as never, partial: false } },
      seq: 5, ts: 100,
    });
    const before = useDashboardStore.getState().metricStates.cpu;
    s.ingestSnapshot({
      groups: { cpu: { status: "unavailable", kind: "permission", reason: "x" } as never },
      seq: 2, ts: 102,
    });
    expect(useDashboardStore.getState().metricStates.cpu).toBe(before);
    expect(useDashboardStore.getState().lastMessageAt).not.toBeNull();
  });
});

describe("connection-local snapshot sequence", () => {
  beforeEach(() => useDashboardStore.getState().reset());

  it("accepts a first snapshot with sequence zero, including after an epoch reset", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot({ seq: 0, ts: 1, groups: {} });
    expect(useDashboardStore.getState().latestSnapshot?.seq).toBe(0);
    expect(useDashboardStore.getState().connectionState).toBe("open");
    store.ingestSnapshot({ seq: 100, ts: 2, groups: {} });
    store.markDisconnected();
    store.beginEpoch();
    store.ingestSnapshot({ seq: 0, ts: 3, groups: {} });
    expect(useDashboardStore.getState().latestSnapshot).toEqual({ seq: 0, ts: 3, groups: {} });
    expect(useDashboardStore.getState().maxSeqSeen).toBe(0);
    expect(useDashboardStore.getState().seqGaps).toEqual([]);
  });

  it("does not advance WS sequence or fabricate gaps when REST fills a disconnected screen", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot({ seq: 100, ts: 1, groups: {} });
    store.markDisconnected();
    const lastMessageAt = useDashboardStore.getState().lastMessageAt;
    store.ingestRestSnapshot({ ts: 2, groups: { cpu: { status: "ok", partial: false, value: { cpu_total: 25 } } } });
    const recovered = useDashboardStore.getState();
    expect(recovered.latestSnapshot?.seq).toBeNull();
    expect(recovered.metricStates.cpu).toEqual({ status: "ok", value: { cpu_total: 25 } });
    expect(recovered.connectionState).toBe("disconnected");
    expect(recovered.maxSeqSeen).toBe(100);
    expect(recovered.lastMessageAt).toBe(lastMessageAt);
    expect(recovered.seqGaps).toEqual([]);
    store.ingestSnapshot({ seq: 101, ts: 3, groups: {} });
    expect(useDashboardStore.getState().maxSeqSeen).toBe(101);
    expect(useDashboardStore.getState().seqGaps).toEqual([]);
  });
});

describe("dashboard history integrity", () => {
  beforeEach(() => useDashboardStore.getState().reset());

  it("keeps unavailable and sequence gaps without inventing zero readings", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot({ seq: 1, ts: 1, groups: { cpu: { status: "ok", partial: false, value: { cpu_total: 10 } } } });
    store.ingestSnapshot({ seq: 2, ts: 2, groups: { cpu: { status: "unavailable", kind: "transient", reason: "Unreadable" } } });
    store.ingestSnapshot({ seq: 4, ts: 4, groups: { cpu: { status: "ok", partial: false, value: { cpu_total: 0 } } } });
    expect(useDashboardStore.getState().cpuHistory).toEqual([10, null, null, 0]);
  });

  it("does not keep a missing group fresh in a full snapshot", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot({ seq: 1, ts: 1, groups: { cpu: { status: "ok", partial: false, value: { cpu_total: 10 } } } });
    store.ingestSnapshot({ seq: 2, ts: 2, groups: {} });
    expect(useDashboardStore.getState().metricStates.cpu.status).toBe("unavailable");
    expect(useDashboardStore.getState().cpuHistory).toEqual([10, null]);
  });

  it("records per-second network rates, not cumulative counters, and bounds them to 60", () => {
    const store = useDashboardStore.getState();
    for (let seq = 1; seq <= 75; seq++) {
      store.ingestSnapshot(
        {
          seq,
          ts: seq,
          groups: {
            network: {
              status: "ok",
              partial: false,
              value: { rx_bytes: seq * 100, tx_bytes: seq * 50 },
            },
          },
        },
        seq * 1000,
      );
    }
    const state = useDashboardStore.getState();
    expect(state.networkHistory).toHaveLength(60);
    expect(state.networkTxHistory).toHaveLength(60);
    // Each one-second interval advances rx by 100 bytes and tx by 50 bytes.
    expect(state.networkHistory[59]).toBeCloseTo(100, 6);
    expect(state.networkTxHistory[59]).toBeCloseTo(50, 6);
    // Only the first sample of the stream has no predecessor, so the bounded
    // window starts with a real rate rather than a fabricated zero.
    expect(state.networkHistory.every((v) => v === null || v >= 0)).toBe(true);
    store.reset();
    expect(state.networkTxHistory).not.toEqual([]);
    expect(useDashboardStore.getState().networkTxHistory).toEqual([]);
    expect(useDashboardStore.getState().networkSample).toBeNull();
  });

  it("derives rates from consecutive counters over monotonic elapsed time", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot(
      { seq: 1, ts: 1, groups: { network: { status: "ok", partial: false, value: { rx_bytes: 1000, tx_bytes: 400 } } } },
      5000,
    );
    store.ingestSnapshot(
      { seq: 2, ts: 2, groups: { network: { status: "ok", partial: false, value: { rx_bytes: 3048, tx_bytes: 1424 } } } },
      6000,
    );
    const state = useDashboardStore.getState();
    expect(state.networkHistory).toEqual([null, 2048]);
    expect(state.networkTxHistory).toEqual([null, 1024]);
  });

  it("drops the baseline when counters reset so the next interval is honest", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot(
      { seq: 1, ts: 1, groups: { network: { status: "ok", partial: false, value: { rx_bytes: 9000, tx_bytes: 9000 } } } },
      1000,
    );
    store.ingestSnapshot(
      { seq: 2, ts: 2, groups: { network: { status: "ok", partial: false, value: { rx_bytes: 10, tx_bytes: 10 } } } },
      2000,
    );
    store.ingestSnapshot(
      { seq: 3, ts: 3, groups: { network: { status: "ok", partial: false, value: { rx_bytes: 1010, tx_bytes: 1010 } } } },
      3000,
    );
    expect(useDashboardStore.getState().networkHistory).toEqual([null, null, 1000]);
  });

  it("keeps no rate while the network group is unavailable", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot(
      { seq: 1, ts: 1, groups: { network: { status: "unavailable", kind: "permission", reason: "denied" } } },
      1000,
    );
    const state = useDashboardStore.getState();
    expect(state.networkHistory).toEqual([null]);
    expect(state.metricStates.network.status).toBe("unavailable");
    expect(state.networkSample).toBeNull();
  });

  it("breaks disk history when the supplied filesystem changes", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot({ seq: 1, ts: 1, groups: { disk: { status: "ok", partial: false, value: { device: "/one", percent: 20 } } } });
    store.ingestSnapshot({ seq: 2, ts: 2, groups: { disk: { status: "ok", partial: false, value: { device: "/two", percent: 30 } } } });
    expect(useDashboardStore.getState().diskHistory).toEqual([20, null, 30]);
  });
});

describe("processes metric state", () => {
  const listA = {
    items: [
      { pid: 10, name: "alpha", cpu_percent: 1, memory_rss_bytes: 1024 },
      { pid: 11, name: "beta", cpu_percent: null, memory_rss_bytes: 2048 },
    ],
    skipped: 0,
  };
  const listB = {
    items: [{ pid: 12, name: "gamma", cpu_percent: 2.5, memory_rss_bytes: 4096 }],
    skipped: 1,
  };

  beforeEach(() => useDashboardStore.getState().reset());

  it("starts loading and returns to loading on reset", () => {
    expect(useDashboardStore.getState().metricStates.processes.status).toBe(
      "loading",
    );
    useDashboardStore.getState().ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: { processes: { status: "ok", partial: false, value: listA } },
    });
    expect(useDashboardStore.getState().metricStates.processes.status).toBe(
      "ok",
    );
    useDashboardStore.getState().reset();
    expect(useDashboardStore.getState().metricStates.processes).toEqual({
      status: "loading",
    });
  });

  it("keeps only the latest list, with no history accumulation", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: { processes: { status: "ok", partial: false, value: listA } },
    });
    store.ingestSnapshot({
      seq: 2,
      ts: 2,
      groups: { processes: { status: "ok", partial: false, value: listB } },
    });
    const state = useDashboardStore.getState();
    expect(state.metricStates.processes).toEqual({
      status: "ok",
      value: listB,
    });
    expect("processesHistory" in state).toBe(false);
  });

  it("maps a partial processes group to the partial state", () => {
    useDashboardStore.getState().ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: { processes: { status: "ok", partial: true, value: listB } },
    });
    expect(useDashboardStore.getState().metricStates.processes).toEqual({
      status: "partial",
      value: listB,
    });
  });

  it("maps an unavailable processes group with its kind and reason", () => {
    useDashboardStore.getState().ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: {
        processes: {
          status: "unavailable",
          kind: "permission",
          reason: "Process listing is not permitted",
        },
      },
    });
    expect(useDashboardStore.getState().metricStates.processes).toEqual({
      status: "unavailable",
      kind: "permission",
      reason: "Process listing is not permitted",
    });
  });

  it("keeps the retained list through stale and disconnected transitions", () => {
    useDashboardStore.getState().ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: { processes: { status: "ok", partial: false, value: listA } },
    });
    useDashboardStore.getState().markStale();
    expect(useDashboardStore.getState().connectionState).toBe("stale");
    expect(useDashboardStore.getState().metricStates.processes).toEqual({
      status: "ok",
      value: listA,
    });
    useDashboardStore.getState().markDisconnected();
    expect(useDashboardStore.getState().connectionState).toBe("disconnected");
    expect(useDashboardStore.getState().metricStates.processes).toEqual({
      status: "ok",
      value: listA,
    });
  });

  it("replaces the list when a reconnect delivers a new snapshot", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: { processes: { status: "ok", partial: false, value: listA } },
    });
    store.markDisconnected();
    store.setConnectionState("open");
    store.ingestSnapshot({
      seq: 2,
      ts: 2,
      groups: { processes: { status: "ok", partial: false, value: listB } },
    });
    expect(useDashboardStore.getState().metricStates.processes).toEqual({
      status: "ok",
      value: listB,
    });
  });

  it("marks processes unavailable when the group is absent from a snapshot", () => {
    const store = useDashboardStore.getState();
    store.ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: { processes: { status: "ok", partial: false, value: listA } },
    });
    store.ingestSnapshot({
      seq: 2,
      ts: 2,
      groups: {
        cpu: { status: "ok", partial: false, value: { cpu_total: 1 } },
      },
    });
    const processes = useDashboardStore.getState().metricStates.processes;
    expect(processes.status).toBe("unavailable");
    if (processes.status === "unavailable") {
      expect(processes.reason).toMatch(/did not include a processes group/i);
    }
  });
});
