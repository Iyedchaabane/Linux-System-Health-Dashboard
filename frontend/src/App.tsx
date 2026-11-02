import React from "react";
import { useDashboardStore } from "./application/store";
import { MetricCard } from "./presentation/components/MetricCard";
import { connectDashboard } from "./application/connect";
import { TimeSeriesChart } from "./presentation/components/TimeSeriesChart";
import { ThemeToggle } from "./presentation/theme/ThemeToggle";
import { useTheme } from "./presentation/theme/ThemeProvider";

function StatusPill() {
  const state = useDashboardStore((s) => s.connectionState);
  const color =
    state === "open"
      ? "bg-ok text-ok"
      : state === "stale"
        ? "bg-warn text-warn"
        : state === "fatal" || state === "disconnected"
          ? "bg-critical text-critical"
          : "bg-muted text-muted";
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>{state}</span>;
}

function LastUpdated() {
  const last = useDashboardStore((s) => s.lastMessageAt);
  const [now, setNow] = React.useState(Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!last) return <span className="text-xs text-muted">Waiting for updates…</span>;
  const seconds = Math.max(0, Math.round((now - last) / 1000));
  return <span className="text-xs text-muted" aria-live="polite">Updated {seconds}s ago</span>;
}

export default function App() {
  const { theme } = useTheme();
  React.useEffect(() => {
    const host = import.meta.env.VITE_E2E === "true" ? "127.0.0.1:8080" : window.location.host;
    const conn = connectDashboard({ socketUrl: `${window.location.protocol === "https:" ? "wss" : "ws"}://${host}/ws/v1/metrics`, fetchSnapshot: async () => {
      const r = await fetch("/api/v1/snapshot");
      return r.json();
    } });
    return () => conn.dispose();
  }, []);
  void theme;
  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden w-64 shrink-0 border-r border-border-subtle bg-surface lg:block">
          <div className="px-4 py-6 text-lg font-semibold text-primary">Health Dashboard</div>
          <nav className="space-y-1 px-2">
            {["Overview", "CPU", "Memory", "Network", "Disks"].map((item) => (
              <div key={item} className="rounded-md px-3 py-2 text-sm text-muted hover:bg-surface-alt hover:text-text">
                {item}
              </div>
            ))}
          </nav>
        </aside>

        {/* Main area */}
        <div className="flex min-h-screen flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-border-subtle bg-surface px-4 py-3">
            <h1 className="text-xl font-semibold text-primary">Linux System Health Dashboard</h1>
            <div className="flex items-center gap-3">
              <StatusPill />
              <LastUpdated />
              <ThemeToggle />
            </div>
          </header>

          <main className="flex-1 p-4 md:p-6">
            <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <MetricCardImpl label="CPU" unit="%" />
              <MetricCardImpl label="Memory" unit="%" />
              <MetricCardImpl label="Disk" unit="%" />
              <MetricCardImpl label="Network" unit="B" />
            </section>
            <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <TimeSeriesChart
                title="CPU usage"
                unit="%"
                data={useDashboardStore((s) => s.cpuHistory)}
              />
              <TimeSeriesChart
                title="Memory used"
                unit="%"
                data={useDashboardStore((s) => s.memoryHistory)}
              />
              <TimeSeriesChart
                title="Disk"
                unit="%"
                data={useDashboardStore((s) => s.diskHistory)}
              />
              <TimeSeriesChart
                title="Network rx"
                unit="B"
                data={useDashboardStore((s) => s.networkHistory)}
              />
            </section>

            <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-card border border-border-subtle bg-surface p-4">
                <h2 className="text-base font-medium text-text">CPU trend (placeholder)</h2>
                <div className="mt-4 h-48 rounded-md border border-border-subtle bg-surface-alt" />
              </div>
              <div className="rounded-card border border-border-subtle bg-surface p-4">
                <h2 className="text-base font-medium text-text">Memory trend (placeholder)</h2>
                <div className="mt-4 h-48 rounded-md border border-border-subtle bg-surface-alt" />
              </div>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}


function MetricCardImpl({ label, unit }: { label: string; unit: string }): React.JSX.Element {
  const groupKey = label === "CPU" ? "cpu" : label === "Memory" ? "memory" : label === "Disk" ? "disk" : label === "Network" ? "network" : "memory";
  const metricState = useDashboardStore((s) => s.metricStates[groupKey]);
  const latest = useDashboardStore((s) => s.latestSnapshot);
  let value: number | null = null;
  let detail = "";
  const groupSym = label === "CPU" ? "cpu" : label === "Memory" ? "memory" : "disk";
  if (latest && (latest.groups[groupSym])?.status === "ok") {
    const group = latest.groups[groupSym];
    if (group && "value" in group && group.value && typeof group.value === "object") {
      const g = group.value as Record<string, number>;
      const v = g.used_percent ?? g.cpu_total ?? g.percent ?? g.rx_bytes ?? null;
      if (typeof v === "number") value = v;
      if (label === "Memory" && typeof g.total === "number" && typeof g.available === "number") {
        detail = `${g.available} of ${g.total}`;
      } else if (label === "Disk" && typeof g.total === "number" && typeof g.used === "number") {
        detail = `${g.used} of ${g.total}`;
      }
    }
  }
  return <MetricCard title={label} unit={unit} metricState={metricState} value={value} detail={detail} />;
}
