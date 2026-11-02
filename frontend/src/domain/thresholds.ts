import type { AlertState } from "./alertState";

export type MetricThresholdKey = "cpu" | "memory" | "disk";

export interface Thresholds {
  warn: number;
  critical: number;
}

/** Default threshold values agreed with the backend (warn 80, critical 95). */
export const DEFAULT_THRESHOLD_VALUES: Thresholds = {
  warn: 80,
  critical: 95,
} as const;

export const DEFAULT_THRESHOLDS: Readonly<Record<MetricThresholdKey, Thresholds>> = {
  cpu: { warn: 80, critical: 95 },
  memory: { warn: 80, critical: 95 },
  disk: { warn: 80, critical: 95 },
} as const;

export function defaultThresholds(metric: MetricThresholdKey): Thresholds {
  return DEFAULT_THRESHOLDS[metric];
}

export function mergeThresholds(
  base: Thresholds,
  overrides?: Partial<Thresholds>,
): Thresholds {
  return {
    warn: overrides?.warn ?? base.warn,
    critical: overrides?.critical ?? base.critical,
  };
}

export function isCritical(value: number, thresholds: Thresholds): boolean {
  return value >= thresholds.critical;
}

export function isWarning(value: number, thresholds: Thresholds): boolean {
  return value >= thresholds.warn && value < thresholds.critical;
}

/** Classify a numeric metric value into an ok / warning / critical severity. */
export function severityFromValue(
  value: number,
  thresholds: Thresholds,
): AlertState {
  if (value >= thresholds.critical) return "critical";
  if (value >= thresholds.warn) return "warning";
  return "ok";
}