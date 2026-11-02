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
    expect(useDashboardStore.getState().maxSeqSeen).toBe(0);
    expect(useDashboardStore.getState().connectionState).toBe("connecting");
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
