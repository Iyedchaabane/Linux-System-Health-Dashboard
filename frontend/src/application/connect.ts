import { MetricsSocket } from "../infrastructure/ws/MetricsSocket";
import { parseServerMessage } from "../infrastructure/ws/schemas";
import { useDashboardStore } from "./store";
import type { GroupState } from "../domain/types";

export type DashboardConnectionOptions = {
  socketUrl: string;
  intervalMs?: number;
  fetchSnapshot?: () => Promise<unknown>;
};

export type DashboardConnection = { dispose: () => void };

function inferSnapshot(payload: unknown): {
  groups: Record<string, unknown>;
  seq: number;
  ts: number;
} | null {
  if (!payload || typeof payload !== "object") return null;
  const obj = payload as Record<string, unknown>;
  const groups = obj.groups;
  if (!groups || typeof groups !== "object") return null;
  const seq = (payload as { seq?: unknown }).seq;
  const ts = (payload as { ts?: unknown }).ts;
  if (typeof seq !== "number" || typeof ts !== "number") return null;
  return { groups: groups as Record<string, unknown>, seq, ts };
}

export function connectDashboard(options: DashboardConnectionOptions): DashboardConnection {
  const recoverSnapshot: () => Promise<void> | void = async () => {
    if (!options.fetchSnapshot) return;
    try {
      const payload = await options.fetchSnapshot();
      const asEnvelope =
        payload && typeof payload === "object" && "v" in payload && "type" in payload
          ? parseServerMessage(payload)
          : null;
      const snapshot = asEnvelope?.type === "snapshot"
        ? inferSnapshot(asEnvelope.data)
        : inferSnapshot(payload);
      if (snapshot) {
        useDashboardStore.getState().ingestSnapshot(snapshot as never);
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
      useDashboardStore.getState().markLastMessage();
      if (msg.type === "hello") {
        const data = msg.data as { interval_ms?: number; groups?: string[] };
        if (typeof data?.interval_ms === "number") {
          useDashboardStore.getState().setConnectionMeta({ intervalMs: data.interval_ms });
        }
      } else if (msg.type === "snapshot") {
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
      switch (state) {
        case "connecting":
          useDashboardStore.getState().setConnectionState("connecting");
          break;
        case "open":
          useDashboardStore.getState().setConnectionState("open");
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
      useDashboardStore.getState().setConnectionMeta({ invalidCount: count });
    },
    onReconnectAttempt: () => {
      // no UI fanfare
    },
  });

  socket.connect();

  return {
    dispose: () => {
      socket.dispose();
    },
  };
}
