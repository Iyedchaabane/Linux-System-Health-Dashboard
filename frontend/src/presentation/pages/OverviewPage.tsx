import React from "react";
import {
  Cpu,
  HardDrive,
  MemoryStick,
  Network,
  Thermometer,
  CircleSlash,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useDashboardStore } from "../../application/store";
import type { MetricState, ScalarMetricGroup } from "../../domain/types";
import { MetricCard } from "../components/MetricCard";
import { ProcessPanel } from "../components/ProcessPanel";
import { Sparkline } from "../components/Sparkline";
import { formatBytes, formatRate } from "../../domain/format";
import { latestRate } from "../../domain/network";

const metrics = {
  cpu: { title: "CPU", icon: Cpu, token: "1", field: "cpu_total" },
  memory: {
    title: "Memory",
    icon: MemoryStick,
    token: "2",
    field: "used_percent",
  },
  disk: { title: "Disk", icon: HardDrive, token: "3", field: "percent" },
  network: { title: "Network", icon: Network, token: "4", field: "rx_bytes" },
} as const;

class PanelBoundary extends React.Component<
  { children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div
        role="alert"
        className="rounded-card border border-border-subtle bg-surface p-3 text-sm text-critical"
      >
        Unable to display this panel. Reload to try again.
      </div>
    ) : (
      this.props.children
    );
  }
}

function MetricPanel({
  groupKey,
  storage = false,
}: {
  groupKey: ScalarMetricGroup;
  storage?: boolean;
}) {
  const metricState = useDashboardStore((s) => s.metricStates[groupKey]);
  const group = useDashboardStore((s) => s.latestSnapshot?.groups[groupKey]);
  const history = useDashboardStore((s) =>
    groupKey === "cpu"
      ? s.cpuHistory
      : groupKey === "memory"
        ? s.memoryHistory
        : groupKey === "disk"
          ? s.diskHistory
          : s.networkHistory,
  );
  const txHistory = useDashboardStore((s) => s.networkTxHistory);
  const connection = useDashboardStore((s) => s.connectionState);
  const { title, icon: Icon, token, field } = metrics[groupKey];
  const raw =
    group?.status === "ok" && group.value && typeof group.value === "object"
      ? (group.value as Record<string, unknown>)
      : null;
  const number = (key: string): number | null =>
    typeof raw?.[key] === "number" && Number.isFinite(raw[key])
      ? (raw[key] as number)
      : null;
  // Network is the only group whose wire value is a cumulative counter, so its
  // card shows the derived rate from the bounded rate history instead.
  const value = groupKey === "network" ? latestRate(history) : number(field);
  const retained = connection !== "open" && group !== undefined;
  const unavailable: MetricState<unknown> = {
    status: "unavailable",
    kind: "unsupported",
    reason: "No reading supplied for this metric.",
  };
  const state: MetricState<unknown> =
    group?.status === "ok" && value === null && groupKey !== "network"
      ? unavailable
      : retained && metricState.status === "ok"
        ? { status: "stale", value: metricState.value }
        : metricState;
  let detail = "";
  if (groupKey === "cpu") {
    const cores = number("core_count");
    const frequency = number("frequency_hz");
    detail = [
      cores !== null ? `${cores} cores` : null,
      frequency !== null ? `${(frequency / 1e9).toFixed(2)} GHz` : null,
    ]
      .filter(Boolean)
      .join(" · ");
  } else if (groupKey === "memory") {
    const total = number("total");
    const available = number("available");
    if (total !== null && available !== null)
      detail = `${formatBytes(total - available)} / ${formatBytes(total)} used`;
  } else if (groupKey === "disk") {
    const device =
      typeof raw?.device === "string"
        ? raw.device
        : "Filesystem identity unavailable";
    detail = `${device} · ${formatBytes(number("used"))} / ${formatBytes(number("total"))} used`;
  } else {
    const txRate = latestRate(txHistory);
    detail =
      txRate === null
        ? "Waiting for a second sample to measure the upload rate"
        : `↑ ${formatRate(txRate)} upload`;
  }
  const unit = groupKey === "network" ? "B/s" : "%";
  return (
    <div className={`min-w-0 ${storage ? "" : "overview-metric"}`}>
      <MetricCard
        title={storage ? "Storage" : title}
        icon={<Icon aria-hidden="true" className="h-4 w-4 text-primary" />}
        unit={unit}
        metricState={state}
        value={value}
        detail={detail}
        valueLabel={groupKey === "network" ? "Download" : undefined}
      >
        {retained && (
          <p className="mt-2 text-xs text-warn">Retained reading · not live</p>
        )}
        {!storage && (
          <div className="mt-auto">
            <Sparkline
              title={`${title} history`}
              unit={unit}
              series={
                groupKey === "network"
                  ? [
                      { label: "Receive", data: history, token },
                      { label: "Transmit", data: txHistory, token: "2" },
                    ]
                  : [{ label: title, data: history, token }]
              }
            />
          </div>
        )}
      </MetricCard>
    </div>
  );
}

function UnavailablePanel({
  title,
  children,
  icon: Icon,
}: {
  title: string;
  children: React.ReactNode;
  icon: LucideIcon;
}) {
  return (
    <section
      className="min-w-0 rounded-card border border-dashed border-border-subtle bg-surface p-3"
      aria-label={title}
    >
      <h2 className="flex items-center gap-2 text-sm font-medium">
        <Icon aria-hidden="true" className="h-4 w-4 text-muted" />
        {title}
      </h2>
      <div className="mt-4 flex items-start gap-2 text-sm text-muted">
        <CircleSlash aria-hidden="true" className="h-4 w-4 shrink-0" />
        <div>
          <p className="font-medium">Unavailable</p>
          <p className="mt-2">{children}</p>
        </div>
      </div>
    </section>
  );
}

export function OverviewPage(): React.JSX.Element {
  return (
    <div className="space-y-4">
      <section
        aria-label="System metrics"
        className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-4"
      >
        {(["cpu", "memory", "disk", "network"] as const).map((key) => (
          <PanelBoundary key={key}>
            <MetricPanel groupKey={key} />
          </PanelBoundary>
        ))}
      </section>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="min-w-0 xl:col-span-2">
          <PanelBoundary>
            <ProcessPanel />
          </PanelBoundary>
        </div>
        <div className="min-w-0 space-y-4">
          <PanelBoundary>
            <MetricPanel groupKey="disk" storage />
          </PanelBoundary>
          <PanelBoundary>
            <UnavailablePanel title="Temperature" icon={Thermometer}>
              Sensor readings are not supplied by the current connection.
            </UnavailablePanel>
          </PanelBoundary>
        </div>
      </div>
    </div>
  );
}

export default OverviewPage;
