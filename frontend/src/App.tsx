import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { useDashboardStore } from "./application/store";
import { connectDashboard } from "./application/connect";
import { ThemeToggle } from "./presentation/theme/ThemeToggle";
import {
  Activity,
  CircleAlert,
  Cpu,
  HardDrive,
  LayoutDashboard,
  MemoryStick,
  Network,
  Radio,
} from "lucide-react";
import { OverviewPage } from "./presentation/pages/OverviewPage";
import { CpuPage } from "./presentation/pages/CpuPage";
import { MemoryPage } from "./presentation/pages/MemoryPage";
import { NetworkPage } from "./presentation/pages/NetworkPage";
import { DisksPage } from "./presentation/pages/DisksPage";

function StatusPill() {
  const state = useDashboardStore((s) => s.connectionState);
  const labels = {
    open: "Live",
    connecting: "Connecting",
    stale: "Stale",
    disconnected: "Disconnected · reconnecting",
    fatal: "Connection error",
  };
  const color =
    state === "open"
      ? "bg-ok/10 text-ok"
      : state === "stale"
        ? "bg-warn/10 text-warn"
        : state === "fatal" || state === "disconnected"
          ? "bg-critical/10 text-critical"
          : "bg-surface-alt text-muted";
  const Icon = state === "open" ? Radio : CircleAlert;
  return (
    <span
      role="status"
      className={`inline-flex items-center gap-2 rounded-full px-2 py-1 text-xs font-medium ${color}`}
    >
      <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
      {labels[state]}
    </span>
  );
}

function ConnectionNotice() {
  const state = useDashboardStore((s) => s.connectionState);
  if (state === "open" || state === "connecting") return null;
  return (
    <div className="mb-4 flex items-center gap-2 rounded-md border border-border-strong bg-surface p-3 text-sm text-warn">
      <CircleAlert aria-hidden="true" className="h-4 w-4 shrink-0" />
      <span>
        {state === "fatal"
          ? "Connection failed. Reload to try again."
          : state === "stale"
            ? "Updates are delayed."
            : "Connection lost. Reconnecting…"}{" "}
        Retained readings are not live.
      </span>
    </div>
  );
}

function LastUpdated() {
  const last = useDashboardStore((s) => s.lastMessageAt);
  const [now, setNow] = React.useState(Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!last)
    return <span className="text-xs text-muted">Waiting for updates…</span>;
  const seconds = Math.max(0, Math.round((now - last) / 1000));
  return <span className="text-xs text-muted">Updated {seconds}s ago</span>;
}

const navItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/cpu", label: "CPU", icon: Cpu },
  { to: "/memory", label: "Memory", icon: MemoryStick },
  { to: "/network", label: "Network", icon: Network },
  { to: "/disks", label: "Disks", icon: HardDrive },
];

export default function App() {
  React.useEffect(() => {
    const e2eApiHost = import.meta.env.VITE_E2E_API as string | undefined;
    const host =
      e2eApiHost ??
      (import.meta.env.VITE_E2E === "true"
        ? "127.0.0.1:8080"
        : window.location.host);
    const snapshotUrl = e2eApiHost
      ? `http://${e2eApiHost}/api/v1/snapshot`
      : "/api/v1/snapshot";
    const conn = connectDashboard({
      socketUrl: `${window.location.protocol === "https:" ? "wss" : "ws"}://${host}/ws/v1/metrics`,
      fetchSnapshot: async () => {
        const r = await fetch(snapshotUrl);
        return r.json();
      },
    });
    return () => conn.dispose();
  }, []);
  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:block focus:p-3"
      >
        Skip to content
      </a>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle bg-surface px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <Activity
            aria-hidden="true"
            className="h-6 w-6 shrink-0 text-primary"
          />
          <h1 className="text-base font-semibold">
            Linux System Health Dashboard
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StatusPill />
          <LastUpdated />
          <ThemeToggle />
        </div>
      </header>
      <div className="flex flex-1">
        <aside className="dashboard-sidebar hidden shrink-0 border-r border-border-subtle bg-surface p-3 lg:block">
          <p className="mb-3 px-3 text-xs font-medium text-muted">MONITOR</p>
          <nav className="space-y-1" aria-label="Primary">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-md px-3 py-3 text-sm ${isActive ? "bg-surface-alt font-semibold text-primary" : "text-muted hover:bg-surface-alt hover:text-text"}`
                }
              >
                <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main
          id="main-content"
          tabIndex={-1}
          className="dashboard-content min-w-0 flex-1 p-4"
        >
          <nav
            className="mb-4 flex flex-wrap gap-1 lg:hidden"
            aria-label="Primary mobile"
          >
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-md px-3 py-3 text-sm ${isActive ? "bg-surface-alt font-semibold text-primary" : "text-muted hover:bg-surface-alt"}`
                }
              >
                <Icon aria-hidden="true" className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <ConnectionNotice />
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/cpu" element={<CpuPage />} />
            <Route path="/memory" element={<MemoryPage />} />
            <Route path="/network" element={<NetworkPage />} />
            <Route path="/disks" element={<DisksPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
