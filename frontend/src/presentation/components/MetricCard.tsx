import type { ReactNode } from "react";
import { CircleDashed, CircleCheck, CircleAlert } from "lucide-react";
import {
  defaultThresholds,
  severityFromValue,
  isCritical,
  isWarning,
} from "../../domain/thresholds";
import { formatBytes, formatPercent, formatRate } from "../../domain/format";
import type { MetricState } from "../../domain/metricState";

export type MetricCardProps = {
  title: string;
  metricState: MetricState<unknown>;
  /**
   * Optional value extractor returning a percentage [0..100] for the threshold
   * indicator. Only used when metricState is ok/partial/stale.
   */
  value: number | null;
  unit?: string;
  detail?: string;
  children?: ReactNode;
  icon?: ReactNode;
  valueLabel?: string;
};

function statusLabel(status: MetricState<unknown>["status"]): string {
  switch (status) {
    case "loading":
      return "Loading";
    case "ok":
      return "OK";
    case "partial":
      return "Partial data";
    case "unavailable":
      return "Unavailable";
    case "stale":
      return "Stale";
    case "disconnected":
      return "Disconnected";
    case "error":
      return "Error";
    default:
      return status;
  }
}

function formatValue(value: number | null, unit?: string): string {
  if (value === null || !Number.isFinite(value)) {
    return "--";
  }
  if (unit === "%") {
    return formatPercent(value);
  }
  if (unit === "B") {
    return formatBytes(value);
  }
  if (unit === "B/s") {
    return formatRate(value);
  }
  return unit ? `${value} ${unit}` : `${value}`;
}

export function MetricCard({
  title,
  metricState,
  value,
  unit,
  detail,
  children,
  icon,
  valueLabel,
}: MetricCardProps) {
  const isPercentage = unit === "%";
  const threshold = defaultThresholds(title === "CPU" ? "cpu" : "memory");
  const hasValue = value !== null && Number.isFinite(value);
  const available =
    hasValue &&
    ["ok", "partial", "stale", "disconnected"].includes(metricState.status);
  // The 0-100 gauge and its Normal/High/Critical label only make sense for
  // percentage metrics. Byte counters have no agreed thresholds, so they are
  // shown as a plain value and never as a bar or a severity.
  const severity =
    available && isPercentage
      ? severityFromValue(value as number, threshold)
      : null;
  const partialReason =
    metricState.status === "partial" ? metricState.reason : undefined;

  return (
    <div
      className={`flex h-full min-w-0 flex-col rounded-card border border-border-subtle bg-surface p-3 ${metricState.status === "unavailable" ? "border-dashed" : ""}`}
      role="article"
      aria-label={`${title} metric`}
      data-status={metricState.status}
    >
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-medium text-muted">
          {icon}
          {title}
        </h2>
        <div className="flex items-center gap-2">
          {metricState.status === "partial" && (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-info/10 px-2 py-0.5 text-xs font-medium text-info"
              title={
                partialReason
                  ? `Partial data: ${partialReason}`
                  : "Only part of this metric could be read"
              }
            >
              <CircleDashed aria-hidden="true" className="h-4 w-4" />
              Partial data
              {partialReason && (
                <span className="sr-only">: {partialReason}</span>
              )}
            </span>
          )}
          {metricState.status !== "partial" && (
            <span className="text-xs font-medium text-muted">
              {statusLabel(metricState.status)}
            </span>
          )}
        </div>
      </header>

      <div className="mt-3">
        {valueLabel && available && (
          <p className="mb-1 text-xs text-muted">{valueLabel}</p>
        )}
        {metricState.status === "loading" ? (
          <div
            className="h-8 w-16 rounded-sm bg-surface-alt"
            role="img"
            aria-label="Waiting for first reading"
          />
        ) : metricState.status === "unavailable" ? (
          <div className="text-sm text-muted">{metricState.reason}</div>
        ) : metricState.status === "error" ? (
          <div className="text-sm text-critical">
            {metricState.message ?? metricState.error}
          </div>
        ) : metricState.status === "stale" ||
          metricState.status === "disconnected" ? (
          <div className="text-2xl font-semibold tabular-nums text-text opacity-60">
            {formatValue(value, unit)}
          </div>
        ) : (
          <div className="text-2xl font-semibold tabular-nums text-text">
            {formatValue(value, unit)}
          </div>
        )}
      </div>

      {available && (
        <div
          className={`mt-3 ${metricState.status === "stale" || metricState.status === "disconnected" ? "opacity-60" : ""}`}
        >
          {isPercentage && (
            <div
              className="h-2 w-full rounded-full bg-border-subtle"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={value as number}
              aria-label={`${title} usage`}
            >
              <div
                className={`h-full rounded-full ${isCritical(value as number, threshold) ? "bg-critical" : isWarning(value as number, threshold) ? "bg-warn" : "bg-ok"}`}
                style={{
                  width: `${Math.min(100, Math.max(0, value as number))}%`,
                }}
              />
            </div>
          )}
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            {isPercentage && (
              <span className="inline-flex items-center gap-1">
                {severity === "ok" ? (
                  <CircleCheck aria-hidden="true" className="h-3 w-3" />
                ) : (
                  <CircleAlert aria-hidden="true" className="h-3 w-3" />
                )}
                {severity === "critical"
                  ? "Critical"
                  : severity === "warning"
                    ? "High"
                    : "Normal"}
              </span>
            )}
            <span className="min-w-0 break-words tabular-nums">
              {detail ?? ""}
            </span>
          </div>
        </div>
      )}
      {available && children}
    </div>
  );
}
