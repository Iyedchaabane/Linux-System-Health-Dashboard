import type {
  GroupState,
  MetricResult,
  MetricState,
  UnavailableKind,
} from "./types";
import { METRIC_STATES } from "./types";

export type MetricStateAction<T> =
  | { type: "load" }
  | { type: "resolve"; value: T; partial?: boolean }
  | { type: "partial"; value: T; reason?: string }
  | { type: "unavailable"; kind: UnavailableKind; reason: string }
  | { type: "stale"; age_ms?: number }
  | { type: "disconnect" }
  | { type: "error"; error: string; message?: string }
  | { type: "reset" };

export function initialMetricState<T>(): MetricState<T> {
  return { status: "loading" };
}

export function toLoading<T>(): MetricState<T> {
  return { status: "loading" };
}

export function toOk<T>(value: T, partial = false): MetricState<T> {
  return partial
    ? { status: "partial", value, reason: undefined }
    : { status: "ok", value };
}

export function toPartial<T>(value: T, reason?: string): MetricState<T> {
  return { status: "partial", value, reason };
}

export function toUnavailable<T>(
  kind: UnavailableKind,
  reason: string,
): MetricState<T> {
  return { status: "unavailable", kind, reason };
}

export function toStale<T>(value: T, age_ms?: number): MetricState<T> {
  return { status: "stale", value, age_ms };
}

export function toDisconnected<T>(): MetricState<T> {
  return { status: "disconnected" };
}

export function toError<T>(error: string, message?: string): MetricState<T> {
  return { status: "error", error, message };
}

export function metricStateFromResult<T>(
  result: MetricResult<T>,
): MetricState<T> {
  if (result.status === "ok") {
    return result.partial
      ? { status: "partial", value: result.value }
      : { status: "ok", value: result.value };
  }
  return {
    status: "unavailable",
    kind: result.kind,
    reason: result.reason,
  };
}

export function metricStateFromGroupState<T>(
  group: GroupState<T>,
): MetricState<T> {
  if (group.status === "ok") {
    const value = group.value as T;
    return group.partial
      ? { status: "partial", value }
      : { status: "ok", value };
  }
  return {
    status: "unavailable",
    kind: group.kind,
    reason: group.reason,
  };
}

export function reduceMetricState<T>(
  current: MetricState<T>,
  action: MetricStateAction<T>,
): MetricState<T> {
  switch (action.type) {
    case "load":
      return { status: "loading" };
    case "resolve":
      return action.partial
        ? { status: "partial", value: action.value }
        : { status: "ok", value: action.value };
    case "partial":
      return { status: "partial", value: action.value, reason: action.reason };
    case "unavailable":
      return {
        status: "unavailable",
        kind: action.kind,
        reason: action.reason,
      };
    case "stale": {
      const value =
        current.status === "ok" ||
        current.status === "partial" ||
        current.status === "stale"
          ? (current as { value: T }).value
          : undefined;
      if (value === undefined) return { status: "stale", value: undefined as T, age_ms: action.age_ms };
      return { status: "stale", value, age_ms: action.age_ms };
    }
    case "disconnect":
      return { status: "disconnected" };
    case "error":
      return { status: "error", error: action.error, message: action.message };
    case "reset":
      return { status: "loading" };
    default: {
      const exhaustive: never = action;
      return exhaustive;
    }
  }
}

export type { MetricState } from "./types";

export function metricStateName(state: MetricState<unknown>): string {
  return state.status;
}

export function isMetricStateLoading<T>(state: MetricState<T>): boolean {
  return state.status === "loading";
}

export const ALL_METRIC_STATES = METRIC_STATES;