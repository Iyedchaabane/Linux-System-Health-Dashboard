import { defaultThresholds, severityFromValue, isCritical, isWarning } from "../../domain/thresholds";
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

export function MetricCard({ title, metricState, value, unit, detail }: MetricCardProps) {
  const threshold = defaultThresholds(title === "CPU" ? "cpu" : "memory");
  const hasValue = value !== null && Number.isFinite(value);
  const severity = hasValue ? severityFromValue(value as number, threshold) : null;

  return (
    <div
      className="rounded-card border border-border-subtle bg-surface p-4"
      role="article"
      aria-label={`${title} metric`}
      data-status={metricState.status}
    >
      <header className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted">{title}</span>
        <span className="text-xs font-medium text-muted">{statusLabel(metricState.status)}</span>
      </header>

      <div className="mt-3">
        {metricState.status === "loading" ? (
          <div className="text-2xl font-semibold tabular-nums text-muted">--</div>
        ) : metricState.status === "unavailable" ? (
          <div className="text-2xl font-semibold tabular-nums text-muted" aria-live="polite">
            {metricState.reason}
          </div>
        ) : metricState.status === "error" ? (
          <div className="text-sm text-critical">{metricState.message ?? metricState.error}</div>
        ) : metricState.status === "stale" ? (
          <div className="text-2xl font-semibold tabular-nums text-text opacity-60">
            {value ?? "--"}
            {unit && <span className="ml-1 text-xs text-muted">{unit}</span>}
          </div>
        ) : (
          <div className="text-2xl font-semibold tabular-nums text-text">
            {value ?? "--"}
            {unit && <span className="ml-1 text-xs text-muted">{unit}</span>}
          </div>
        )}
      </div>

      {hasValue && (
        <div className="mt-3">
          <div className="h-2 w-full rounded-full bg-border-subtle" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value as number} aria-label={`${title} usage`}>
            <div
              className={`h-full rounded-full ${isCritical(value as number, threshold) ? "bg-critical" : isWarning(value as number, threshold) ? "bg-warn" : "bg-ok"}`}
              style={{ width: `${Math.min(100, Math.max(0, value as number))}%` }}
            />
          </div>
          <div className="mt-1 flex items-center justify-between text-xs text-muted">
            <span>
              {severity === "critical" ? "Critical" : severity === "warning" ? "High" : "Normal"}
            </span>
            <span>{detail ?? ""}</span>
          </div>
        </div>
      )}
    </div>
  );
}
