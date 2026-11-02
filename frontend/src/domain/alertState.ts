/** UI severity vocabulary, separate from the data MetricState. */

export type AlertState =
  | "ok"
  | "warning"
  | "critical"
  | "info";

/** Alias clarifying that this is a UI severity, not a backend AlertState band only. */
export type UiSeverity = AlertState;

export const ALERT_STATES = [
  "ok",
  "warning",
  "critical",
  "info",
] as const satisfies readonly AlertState[];

export const BACKEND_ALERT_STATES = ["ok", "warning", "critical"] as const;