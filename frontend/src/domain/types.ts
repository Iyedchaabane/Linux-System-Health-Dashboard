/** Pure domain types mirroring the backend metric contract. */

/** Reason a metric result is unavailable. Mirrors UnavailableKind. */
export type UnavailableKind =
  | "unsupported"
  | "permission"
  | "transient"
  | "disabled";

/** Metric value as sent on the wire (ok | unavailable). */
export type MetricResult<T> =
  | { status: "ok"; value: T; partial?: boolean }
  | { status: "unavailable"; kind: UnavailableKind; reason: string };

/** Alias used by react-dashboard domain code. */
export type MetricValue<T> = MetricResult<T>;

/** CPU metric value (wire shape). */
export interface CpuSnapshot {
  cpu_total: number;
  per_core: Array<number | null>;
  load_average: number;
  core_count: number;
  frequency_hz: number | null;
}

/** Memory metric value (wire shape). */
export interface MemorySnapshot {
  total: number;
  available: number;
  used_percent: number;
}

/** Disk (filesystem) snapshot value sent on the wire. */
export interface DiskSnapshot {
  device: string;
  total: number;
  used: number;
  percent: number;
}

/** Cumulative network counters sent on the wire. */
export interface NetworkSnapshot {
  rx_bytes: number;
  tx_bytes: number;
}

/** One process row as sent on the wire. `cpu_percent` is null until measured. */
export interface ProcessRow {
  pid: number;
  name: string;
  cpu_percent: number | null;
  memory_rss_bytes: number;
}

/** Bounded current process list; not a historical series. */
export interface ProcessList {
  items: ProcessRow[];
  /** Total processes visible on the host; `items` may be a bounded subset. */
  total: number;
  skipped: number;
}

/** Group states on the WebSocket/REST contract. */
export type GroupState<TValue> =
  | { status: "ok"; value: TValue | null; partial: boolean }
  | { status: "unavailable"; kind: UnavailableKind; reason: string };

/** Scalar metric groups rendered as cards. */
export type ScalarMetricGroup = "cpu" | "memory" | "disk" | "network";

/** Group names currently exposed by the backend. */
export type MetricGroup = ScalarMetricGroup | "processes";

/** Implemented metric groups. */
export const METRIC_GROUPS: readonly MetricGroup[] = [
  "cpu",
  "memory",
  "disk",
  "network",
  "processes",
] as const;

/** The protocol version sent on every message. */
export const PROTOCOL_VERSION = 1 as const;

/** The seven mutually exclusive UI states for one metric. */
export type ConnectionStatus = "connecting" | "open" | "stale" | "disconnected" | "fatal";

/** The seven mutually exclusive UI states for one metric. */
export type MetricState<T> =
  | { status: "loading" }
  | { status: "ok"; value: T; partial?: boolean }
  | { status: "partial"; value: T; reason?: string }
  | { status: "unavailable"; kind: UnavailableKind; reason: string }
  | { status: "stale"; value: T; age_ms?: number }
  | { status: "disconnected" }
  | { status: "error"; error: string; message?: string };

/** All metric state names, kept in order for exhaustive handling. */
export const METRIC_STATES = [
  "loading",
  "ok",
  "partial",
  "unavailable",
  "stale",
  "disconnected",
  "error",
] as const;

export type MetricStateName = (typeof METRIC_STATES)[number];

/** Wall-clock typed helper for monotonic seconds used by thresholding. */
export type MonotonicSeconds = number;