import React from "react";
import { useDashboardStore } from "../../application/store";
import { MetricCard } from "../components/MetricCard";
import { TimeSeriesChart } from "../components/TimeSeriesChart";
import { formatBytes } from "../../domain/format";

export function DisksPage(): React.JSX.Element {
  const metricState = useDashboardStore((s) => s.metricStates.disk);
  const latest = useDashboardStore((s) => s.latestSnapshot);
  const history = useDashboardStore((s) => s.diskHistory);
  let value: number | null = null;
  let detail = "";
  const group = latest?.groups?.disk;
  if (group && group.status === "ok" && group.value && typeof group.value === "object") {
    const g = group.value as Record<string, unknown>;
    if (typeof g.percent === "number") value = g.percent;
    if (typeof g.total === "number" && typeof g.used === "number") {
      detail = `${formatBytes(g.used)} of ${formatBytes(g.total)}`;
    }
  }
  return (
    <>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <MetricCard title="Disk" unit="%" metricState={metricState} value={value} detail={detail} />
      </section>
      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TimeSeriesChart title="Disk" unit="%" data={history} />
      </section>
    </>
  );
}

export default DisksPage;