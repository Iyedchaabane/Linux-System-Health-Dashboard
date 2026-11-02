import { describe, expect, it } from "vitest";
import {
  initialMetricState,
  metricStateFromGroupState,
  reduceMetricState,
  toDisconnected,
  toError,
  toLoading,
  toOk,
  toPartial,
  toStale,
  toUnavailable,
} from "../../src/domain/metricState";
import { METRIC_STATES } from "../../src/domain/types";

describe("MetricState", () => {
  it("defines exactly seven states", () => {
    expect(METRIC_STATES).toHaveLength(7);
    expect(new Set(METRIC_STATES).size).toBe(7);
  });

  it("initial state is loading", () => {
    expect(initialMetricState<number>().status).toBe("loading");
  });

  it("factories produce each state", () => {
    expect(toLoading<number>().status).toBe("loading");
    expect(toOk(42).status).toBe("ok");
    expect(toPartial(42).status).toBe("partial");
    expect(toUnavailable("permission", "reason").status).toBe("unavailable");
    expect(toStale(42).status).toBe("stale");
    expect(toDisconnected<number>().status).toBe("disconnected");
    expect(toError<number>("boom").status).toBe("error");
  });

  it("reducer transitions through all states", () => {
    let state = initialMetricState<number>();
    state = reduceMetricState(state, { type: "resolve", value: 10 });
    expect(state).toMatchObject({ status: "ok", value: 10 });
    state = reduceMetricState(state, { type: "partial", value: 10, reason: "missing core" });
    expect(state).toMatchObject({ status: "partial" });
    state = reduceMetricState(state, { type: "unavailable", kind: "permission", reason: "no access" });
    expect(state).toMatchObject({ status: "unavailable" });
    state = reduceMetricState(state, { type: "error", error: "boom" });
    expect(state).toMatchObject({ status: "error" });
    state = reduceMetricState(state, { type: "disconnect" });
    expect(state.status).toBe("disconnected");
    state = reduceMetricState(state, { type: "load" });
    expect(state.status).toBe("loading");
  });

  it("converts an ok wire group into a partial state when partial", () => {
    const result = metricStateFromGroupState<number>({ status: "ok", value: 5, partial: true });
    expect(result.status).toBe("partial");
  });

  it("converts an unavailable wire group", () => {
    const result = metricStateFromGroupState<number>({
      status: "unavailable",
      kind: "transient",
      reason: "blip",
    });
    expect(result).toMatchObject({ status: "unavailable", kind: "transient" });
  });
});