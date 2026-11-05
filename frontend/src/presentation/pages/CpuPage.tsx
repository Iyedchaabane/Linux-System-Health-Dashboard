import React from "react";
import { useDashboardStore } from "../../application/store";
import { MetricCard } from "../components/MetricCard";
import { TimeSeriesChart } from "../components/TimeSeriesChart";

export function CpuPage(): React.JSX.Element {
  const metricState = useDashboardStore((s) => s.metricStates.cpu);
  const latest = useDashboardStore((s) => s.latestSnapshot);
  const history = useDashboardStore((s) => s.cpuHistory);
  let value: number | null = null;
  let detail = "";
  const group = latest?.groups?.cpu;
  if (group && group.status === "ok" && group.value && typeof group.value === "object") {
    const g = group.value as Record<string, unknown>;
    if (typeof g.cpu_total === "number") value = g.cpu_total;
    if (typeof g.core_count === "number") detail = `${g.core_count} cores`;
  }
  return (
    <>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <MetricCard title="CPU" unit="%" metricState={metricState} value={value} detail={detail} />
      </section>
      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TimeSeriesChart title="CPU usage" unit="%" data={history} />
      </section>
    </>
  );
}

export default CpuPage;