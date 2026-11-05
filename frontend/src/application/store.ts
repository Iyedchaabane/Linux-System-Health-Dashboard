import { create } from "zustand";

import type {
  ConnectionStatus,
  CpuSnapshot,
  GroupState,
  DiskSnapshot,
  MemorySnapshot,
  NetworkSnapshot,
  ProcessList,
  MetricGroup,
} from "../domain/types";
import { metricStateFromGroupState, type MetricState } from "../domain/metricState";
import {
  computeNetworkRates,
  isValidCounters,
  type NetworkCountersSample,
} from "../domain/network";

export type StoredSnapshot = {
  groups: Record<string, GroupState<unknown>>;
  seq: number | null;
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
    processes: MetricState<ProcessList>;
  };
  cpuHistory: (number | null)[];
  memoryHistory: (number | null)[];
  diskHistory: (number | null)[];
  networkHistory: (number | null)[];
  networkTxHistory: (number | null)[];
  /** Last cumulative counters plus monotonic receipt time, used to derive rates. */
  networkSample: NetworkCountersSample | null;
  seqGaps: number[];
  maxSeqSeen: number;

  setConnectionMeta: (meta: { intervalMs?: number; droppedCount?: number; invalidCount?: number }) => void;
  setConnectionState: (state: ConnectionStatus) => void;
  markLastMessage: (timestamp?: number) => void;
  beginEpoch: () => void;
  ingestRestSnapshot: (snapshot: Omit<StoredSnapshot, "seq">) => void;
  ingestSnapshot: (snapshot: StoredSnapshot, receivedAt?: number) => void;
  markStale: () => void;
  markDisconnected: (fatal?: boolean) => void;
  reset: () => void;
};

const INITIAL_METRIC_STATE = { cpu: { status: "loading" } as MetricState<CpuSnapshot>, memory: { status: "loading" } as MetricState<MemorySnapshot>, disk: { status: "loading" } as MetricState<DiskSnapshot>, network: { status: "loading" } as MetricState<NetworkSnapshot>, processes: { status: "loading" } as MetricState<ProcessList> };

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
  networkTxHistory: [],
  networkSample: null,
  seqGaps: [],
  maxSeqSeen: -1,

  setConnectionMeta: (meta) =>
    set((s) => ({
      intervalMs: meta.intervalMs ?? s.intervalMs,
      droppedCount: meta.droppedCount ?? s.droppedCount,
      invalidCount: meta.invalidCount ?? s.invalidCount,
    })),

  setConnectionState: (state) => set({ connectionState: state }),

  markLastMessage: (timestamp) => set({ lastMessageAt: timestamp ?? Date.now() }),

  beginEpoch: () => set({ maxSeqSeen: -1, seqGaps: [], networkSample: null, connectionState: "connecting" }),

  // REST has no connection-local sequence and cannot establish a live stream.
  ingestRestSnapshot: (snapshot) => get().ingestSnapshot({ ...snapshot, seq: null }),

  ingestSnapshot: (snapshot, receivedAt) => {
    const receivedAtMs =
      receivedAt ?? (typeof performance !== "undefined" ? performance.now() : Date.now());
    const previousMax = get().maxSeqSeen;
    // Reject older or duplicate snapshots without modifying state.
    if (snapshot.seq !== null && snapshot.seq <= previousMax) {
      return;
    }
    const CPU_GROUP: MetricGroup = "cpu";
    const MEMORY_GROUP: MetricGroup = "memory";
    const groups = snapshot.groups;

    const cpuRaw = (groups["cpu"] ?? groups[CPU_GROUP]) as GroupState<CpuSnapshot> | undefined;
    const memoryRaw = (groups["memory"] ?? groups[MEMORY_GROUP]) as GroupState<MemorySnapshot> | undefined;
    const diskRaw = (groups["disk"]) as GroupState<DiskSnapshot> | undefined;
    const networkRaw = (groups["network"]) as GroupState<NetworkSnapshot> | undefined;
    const processesRaw = (groups["processes"]) as GroupState<ProcessList> | undefined;

    const cpuState = cpuRaw ? metricStateFromGroupState<CpuSnapshot>(cpuRaw) : null;
    const memoryState = memoryRaw ? metricStateFromGroupState<MemorySnapshot>(memoryRaw) : null;
    const diskState = diskRaw ? metricStateFromGroupState<DiskSnapshot>(diskRaw) : null;
    const networkState = networkRaw ? metricStateFromGroupState<NetworkSnapshot>(networkRaw) : null;
    const processesState = processesRaw
      ? metricStateFromGroupState<ProcessList>(processesRaw)
      : null;

    // sequence gap detection
    const seqGaps: number[] = [];
    const maxSeqSeen = get().maxSeqSeen;
    if (snapshot.seq !== null && maxSeqSeen >= 0 && snapshot.seq > maxSeqSeen + 1) {
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
      // Preserve missing readings and sequence gaps instead of connecting across them.
      const append = (history: (number | null)[], value: number | undefined, changedSource = false) =>
        [...history, ...(seqGaps.length > 0 || changedSource ? [null] : []), value !== undefined && Number.isFinite(value) ? value : null].slice(-60);
      const netRaw = groups["network"];
      const net = netRaw?.status === "ok" ? (netRaw.value as NetworkSnapshot | null) : null;
      // Rates come from consecutive cumulative counters over monotonic time.
      // Missing, reset or invalid intervals yield null (a gap), never zero.
      const currentSample: NetworkCountersSample | null =
        net && isValidCounters(net)
          ? { rxBytes: net.rx_bytes, txBytes: net.tx_bytes, at: receivedAtMs }
          : null;
      const rates = computeNetworkRates(s.networkSample, currentSample);
      const previousDisk = s.latestSnapshot?.groups.disk;
      const diskChanged = previousDisk?.status === "ok" && diskRaw?.status === "ok" &&
        (previousDisk.value as DiskSnapshot | null)?.device !== diskRaw.value?.device;
      const nextCpu = append(s.cpuHistory, cpuVal);
      const nextMem = append(s.memoryHistory, memVal);
      const nextDisk = append(s.diskHistory, diskVal, diskChanged);
      const nextNet = append(s.networkHistory, rates?.rxBytesPerSecond);
      const nextTx = append(s.networkTxHistory, rates?.txBytesPerSecond);
      return {
      latestSnapshot: {
        groups: snapshot.groups,
        seq: snapshot.seq,
        ts: snapshot.ts,
      },
      metricStates: {
        cpu: (cpuState ?? { status: "unavailable", kind: "unsupported", reason: "No reading supplied for this metric." }) as MetricState<CpuSnapshot>,
        memory: (memoryState ?? { status: "unavailable", kind: "unsupported", reason: "No reading supplied for this metric." }) as MetricState<MemorySnapshot>,
        disk: (diskState ?? { status: "unavailable", kind: "unsupported", reason: "No reading supplied for this metric." }) as MetricState<DiskSnapshot>,
        network: (networkState ?? { status: "unavailable", kind: "unsupported", reason: "No reading supplied for this metric." }) as MetricState<NetworkSnapshot>,
        processes: (processesState ?? {
          status: "unavailable",
          kind: "unsupported",
          reason: "The server did not include a processes group in this snapshot.",
        }) as MetricState<ProcessList>,
      },
      lastMessageAt: snapshot.seq === null ? s.lastMessageAt : Date.now(),
      connectionState: snapshot.seq === null ? s.connectionState : "open",
      cpuHistory: nextCpu,
      memoryHistory: nextMem,
      diskHistory: nextDisk,
      networkHistory: nextNet,
      networkTxHistory: nextTx,
      // A gap (unavailable group, counter reset) drops the baseline so the next
      // reading starts a fresh interval instead of averaging across the outage.
      networkSample: currentSample,
      seqGaps: [...s.seqGaps, ...seqGaps],
      maxSeqSeen: snapshot.seq === null ? s.maxSeqSeen : snapshot.seq,
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
      cpuHistory: [],
      memoryHistory: [],
      diskHistory: [],
      networkHistory: [],
      networkTxHistory: [],
      networkSample: null,
      seqGaps: [],
      maxSeqSeen: -1,
    }),
}));
