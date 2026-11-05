import { MetricsSocket } from "../infrastructure/ws/MetricsSocket";
import { SnapshotGroupsSchema, SnapshotMetaSchema, z } from "../infrastructure/ws/schemas";
import { useDashboardStore } from "./store";
import type { GroupState } from "../domain/types";

export type DashboardConnectionOptions = {
  socketUrl: string;
  intervalMs?: number;
  fetchSnapshot?: () => Promise<unknown>;
};

export type DashboardConnection = { dispose: () => void };

const RestSnapshotSchema = z.object({
  ts: z.number().int().min(0),
  groups: SnapshotGroupsSchema,
  meta: SnapshotMetaSchema.nullable().optional(),
});

export function connectDashboard(options: DashboardConnectionOptions): DashboardConnection {
  let disposed = false;
  let snapshotRevision = 0;
  const recoverSnapshot = async (isCurrent: () => boolean): Promise<void> => {
    if (!options.fetchSnapshot) return;
    const revision = snapshotRevision;
    try {
      const payload = await options.fetchSnapshot();
      if (disposed || !isCurrent() || revision !== snapshotRevision) return;
      const snapshot = RestSnapshotSchema.safeParse(payload);
      if (snapshot.success) {
        useDashboardStore.getState().ingestRestSnapshot(snapshot.data);
      }
    } catch {
      // recovery failure should not crash the socket loop
    }
  };

  const socket = new MetricsSocket({
    url: options.socketUrl,
    intervalMs: options.intervalMs ?? 1000,
    recover: recoverSnapshot,
    onMessage: (msg) => {
      if (disposed) return;
      useDashboardStore.getState().markLastMessage();
      if (msg.type === "hello") {
        useDashboardStore.getState().beginEpoch();
        const data = msg.data as { interval_ms?: number; groups?: string[] };
        if (typeof data?.interval_ms === "number") {
          useDashboardStore.getState().setConnectionMeta({ intervalMs: data.interval_ms });
        }
      } else if (msg.type === "snapshot") {
        snapshotRevision += 1;
        const data = msg.data as { groups?: Record<string, unknown>; meta?: { dropped_since_last?: number | null } };
        useDashboardStore.getState().ingestSnapshot({
          groups: (data?.groups ?? {}) as Record<string, GroupState<unknown>>,
          seq: msg.seq,
          ts: msg.ts,
        });
        if (typeof data?.meta?.dropped_since_last === "number") {
          useDashboardStore.getState().setConnectionMeta({ droppedCount: data.meta.dropped_since_last });
        }
      } else if (msg.type === "error") {
        // parsed + acknowledged
      }
    },
    onStateChange: (state, reason) => {
      if (disposed) return;
      switch (state) {
        case "connecting":
          useDashboardStore.getState().setConnectionState("connecting");
          break;
        case "open":
          // Transport open (or hello) is not a fresh metric reading.
          useDashboardStore.getState().setConnectionState("connecting");
          break;
        case "stale":
          useDashboardStore.getState().setConnectionState("stale");
          useDashboardStore.getState().markStale();
          break;
        case "fatal":
          useDashboardStore.getState().setConnectionState("fatal" as never);
          useDashboardStore.getState().markDisconnected(true);
          break;
        case "closed":
        default:
          useDashboardStore.getState().setConnectionState("disconnected");
          useDashboardStore.getState().markDisconnected();
          break;
      }
      void reason;
    },
    onInvalidMessage: (count) => {
      if (disposed) return;
      useDashboardStore.getState().setConnectionMeta({ invalidCount: count });
    },
    onReconnectAttempt: () => {
      // no UI fanfare
    },
  });

  socket.connect();

  return {
    dispose: () => {
      disposed = true;
      socket.dispose();
    },
  };
}
