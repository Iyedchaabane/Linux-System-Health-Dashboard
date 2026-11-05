import React from "react";
import { useDashboardStore } from "../../application/store";
import { MetricCard } from "../components/MetricCard";
import { TimeSeriesChart } from "../components/TimeSeriesChart";
import { formatRate } from "../../domain/format";
import { latestRate } from "../../domain/network";

export function NetworkPage(): React.JSX.Element {
  const metricState = useDashboardStore((s) => s.metricStates.network);
  const rxHistory = useDashboardStore((s) => s.networkHistory);
  const txHistory = useDashboardStore((s) => s.networkTxHistory);

  // The wire carries cumulative counters; the cards show derived per-second
  // rates. Until a second sample exists there is no rate, so the value is
  // absent rather than zero.
  const download = latestRate(rxHistory);
  const upload = latestRate(txHistory);

  return (
    <>
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <MetricCard
          title="Download"
          unit="B/s"
          metricState={metricState}
          value={download}
          detail={upload === null ? "" : `↑ ${formatRate(upload)}`}
        />
        <MetricCard
          title="Upload"
          unit="B/s"
          metricState={metricState}
          value={upload}
          detail={download === null ? "" : `↓ ${formatRate(download)}`}
        />
      </section>
      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TimeSeriesChart title="Network receive" unit="B/s" data={rxHistory} domain={[0, "auto"]} />
        <TimeSeriesChart title="Network transmit" unit="B/s" data={txHistory} domain={[0, "auto"]} />
      </section>
    </>
  );
}

export default NetworkPage;
