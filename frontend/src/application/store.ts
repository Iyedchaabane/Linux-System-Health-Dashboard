import { create } from "zustand";

import type {
  ConnectionStatus,
  CpuSnapshot,
  GroupState,
  DiskSnapshot,
  MemorySnapshot,
  NetworkSnapshot,
  MetricGroup,
} from "../domain/types";
import { metricStateFromGroupState, type MetricState } from "../domain/metricState";

export type StoredSnapshot = {
  groups: Record<string, GroupState<unknown>>;
  seq: number;
  ts: number;
};

export type DashboardState = {
  connectionState: ConnectionStatus;
  lastMessageAt: number | null;
  intervalMs: number;
  droppedCount: number;
  invalidCount: number;
  latestSnapshot: StoredSnapshot | null;
  metricStates: {
    cpu: MetricState<CpuSnapshot>;
    memory: MetricState<MemorySnapshot>;
    disk: MetricState<DiskSnapshot>;
    network: MetricState<NetworkSnapshot>;
  };
  cpuHistory: number[];
  memoryHistory: number[];
  diskHistory: number[];
  networkHistory: number[];
  seqGaps: number[];
  maxSeqSeen: number;

  setConnectionMeta: (meta: { intervalMs?: number; droppedCount?: number; invalidCount?: number }) => void;
  setConnectionState: (state: ConnectionStatus) => void;
  markLastMessage: (timestamp?: number) => void;
  ingestSnapshot: (snapshot: StoredSnapshot) => void;
  markStale: () => void;
  markDisconnected: (fatal?: boolean) => void;
  reset: () => void;
};

const INITIAL_METRIC_STATE = { cpu: { status: "loading" } as MetricState<CpuSnapshot>, memory: { status: "loading" } as MetricState<MemorySnapshot>, disk: { status: "loading" } as MetricState<DiskSnapshot>, network: { status: "loading" } as MetricState<NetworkSnapshot> };

export const useDashboardStore = create<DashboardState>((set, get) => ({
  connectionState: "connecting",
  lastMessageAt: null,
  intervalMs: 1000,
  droppedCount: 0,
  invalidCount: 0,
  latestSnapshot: null,
  metricStates: { ...INITIAL_METRIC_STATE },
  cpuHistory: [] as number[],
  memoryHistory: [] as number[],
  diskHistory: [] as number[],
  networkHistory: [] as number[],
  seqGaps: [],
  maxSeqSeen: 0,

  setConnectionMeta: (meta) =>
    set((s) => ({
      intervalMs: meta.intervalMs ?? s.intervalMs,
      droppedCount: meta.droppedCount ?? s.droppedCount,
      invalidCount: meta.invalidCount ?? s.invalidCount,
    })),

  setConnectionState: (state) => set({ connectionState: state }),

  markLastMessage: (timestamp) => set({ lastMessageAt: timestamp ?? Date.now() }),

  ingestSnapshot: (snapshot) => {
    const previousMax = get().maxSeqSeen;
    // Reject older or duplicate snapshots without modifying state.
    if (previousMax > 0 && snapshot.seq < previousMax) {
      return;
    }
    // A duplicate sequence number must not overwrite newer data.
    if (previousMax > 0 && snapshot.seq === previousMax) {
      return;
    }
    const CPU_GROUP: MetricGroup = "cpu";
    const MEMORY_GROUP: MetricGroup = "memory";
    const groups = snapshot.groups;

    const cpuRaw = (groups["cpu"] ?? groups[CPU_GROUP]) as GroupState<CpuSnapshot> | undefined;
    const memoryRaw = (groups["memory"] ?? groups[MEMORY_GROUP]) as GroupState<MemorySnapshot> | undefined;
    const diskRaw = (groups["disk"]) as GroupState<DiskSnapshot> | undefined;
    const networkRaw = (groups["network"]) as GroupState<NetworkSnapshot> | undefined;

    const cpuState = cpuRaw ? metricStateFromGroupState<CpuSnapshot>(cpuRaw) : null;
    const memoryState = memoryRaw ? metricStateFromGroupState<MemorySnapshot>(memoryRaw) : null;
    const diskState = diskRaw ? metricStateFromGroupState<DiskSnapshot>(diskRaw) : null;
    const networkState = networkRaw ? metricStateFromGroupState<NetworkSnapshot>(networkRaw) : null;

    // sequence gap detection
    const seqGaps: number[] = [];
    const maxSeqSeen = get().maxSeqSeen;
    if (maxSeqSeen > 0 && snapshot.seq > maxSeqSeen + 1) {
      for (let seq = maxSeqSeen + 1; seq < snapshot.seq; seq += 1) {
        seqGaps.push(seq);
      }
    }

    // deriv values
    const cpuVal = (() => {
      const g = groups["cpu"];
      if (g && g.status === "ok" && g.value && typeof (g.value as { cpu_total?: unknown }).cpu_total === "number") {
        return (g.value as { cpu_total: number }).cpu_total;
      }
      return undefined;
    })();
    const diskVal = (() => {
      const g = groups["disk"];
      if (g && g.status === "ok" && g.value && typeof (g.value as { percent?: unknown }).percent === "number") {
        return (g.value as { percent: number }).percent;
      }
      return undefined;
    })();

    const memVal = (() => {
      const g = groups["memory"];
      if (g && g.status === "ok" && g.value && typeof (g.value as { used_percent?: unknown }).used_percent === "number") {
        return (g.value as { used_percent: number }).used_percent;
      }
      return undefined;
    })();

    set((s) => {
      const nextCpu = cpuVal === undefined ? s.cpuHistory : [...s.cpuHistory, cpuVal].slice(-60);
      const nextMem = memVal === undefined ? s.memoryHistory : [...s.memoryHistory, memVal].slice(-60);
      const nextDisk = diskVal === undefined ? s.diskHistory : [...s.diskHistory, diskVal].slice(-60);
    const netRaw = groups["network"];
    const netVal = (netRaw && netRaw.status === "ok" && netRaw.value && typeof (netRaw.value as { rx_bytes?: unknown }).rx_bytes === "number")
      ? (netRaw.value as { rx_bytes: number }).rx_bytes
      : undefined;
    const nextNet = netVal === undefined ? s.networkHistory : [...s.networkHistory, netVal].slice(-60);
      return {
      latestSnapshot: {
        groups: snapshot.groups,
        seq: snapshot.seq,
        ts: snapshot.ts,
      },
      metricStates: {
        cpu: (cpuState ?? s.metricStates.cpu) as MetricState<CpuSnapshot>,
        memory: (memoryState ?? s.metricStates.memory) as MetricState<MemorySnapshot>,
        disk: (diskState ?? s.metricStates.disk) as MetricState<DiskSnapshot>,
        network: (networkState ?? s.metricStates.network) as MetricState<NetworkSnapshot>,
      },
      lastMessageAt: Date.now(),
      cpuHistory: nextCpu,
      memoryHistory: nextMem,
      diskHistory: nextDisk,
      networkHistory: nextNet,
      seqGaps: [...s.seqGaps, ...seqGaps],
      maxSeqSeen: Math.max(s.maxSeqSeen, snapshot.seq),
    };});
  },

  markStale: () => set({ connectionState: "stale" }),
  markDisconnected: (fatal) =>
    set({ connectionState: fatal ? "fatal" : "disconnected" }),
  reset: () =>
    set({
      connectionState: "connecting",
      lastMessageAt: null,
      intervalMs: 1000,
      droppedCount: 0,
      invalidCount: 0,
      latestSnapshot: null,
      metricStates: { ...INITIAL_METRIC_STATE },
      seqGaps: [],
      maxSeqSeen: 0,
    }),
}));
