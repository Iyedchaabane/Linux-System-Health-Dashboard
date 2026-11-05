import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OverviewPage } from "../../src/presentation/pages/OverviewPage";
import { useDashboardStore } from "../../src/application/store";
import type { GroupState } from "../../src/domain/types";

function seed() {
  const store = useDashboardStore.getState();
  store.setConnectionState("open");
  const groups: Record<string, GroupState<unknown>> = {
      cpu: {
        status: "ok",
        partial: false,
        value: { cpu_total: 28, core_count: 8, frequency_hz: 3200000000 },
      },
      memory: {
        status: "ok",
        partial: false,
        value: {
          total: 8 * 1024 ** 3,
          available: 2 * 1024 ** 3,
          used_percent: 75,
        },
      },
      disk: {
        status: "ok",
        partial: false,
        value: {
          device: "/test-volume",
          total: 100 * 1024 ** 3,
          used: 40 * 1024 ** 3,
          percent: 40,
        },
      },
      network: {
        status: "ok",
        partial: false,
        value: { rx_bytes: 4096, tx_bytes: 2048 },
      },
  };
  // Two samples one second apart are the minimum needed to derive a rate:
  // the second advances rx by 2 KiB and tx by 1 KiB, so 2 KiB/s and 1 KiB/s.
  store.ingestSnapshot({ seq: 1, ts: 1000, groups }, 0);
  store.ingestSnapshot(
    {
      seq: 2,
      ts: 2000,
      groups: {
        ...groups,
        network: {
          status: "ok",
          partial: false,
          value: { rx_bytes: 4096 + 2048, tx_bytes: 2048 + 1024 },
        },
      },
    },
    1000,
  );
}

describe("compact overview", () => {
  afterEach(() => vi.restoreAllMocks());
  beforeEach(() => {
    useDashboardStore.getState().reset();
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      width: 240,
      height: 96,
      top: 0,
      left: 0,
      right: 240,
      bottom: 96,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
  });

  it("keeps each history inside its metric and labels memory as used capacity", () => {
    seed();
    render(<OverviewPage />);
    const metrics = within(
      screen.getByRole("region", { name: "System metrics" }),
    );
    expect(metrics.getAllByRole("article")).toHaveLength(4);
    for (const title of ["CPU", "Memory", "Disk", "Network"]) {
      expect(
        within(
          metrics.getByRole("article", { name: `${title} metric` }),
        ).getByRole("img", { name: new RegExp(`${title} history`) }),
      ).toBeTruthy();
    }
    expect(screen.getByText("6.00 GiB / 8.00 GiB used")).toBeTruthy();
    expect(screen.getByText("8 cores · 3.20 GHz")).toBeTruthy();
  });

  it("shows derived download and upload rates with per-second units and exposes both histories by keyboard", async () => {
    seed();
    const user = userEvent.setup();
    render(<OverviewPage />);
    const card = screen.getByRole("article", { name: "Network metric" });
    expect(within(card).getByText("Download")).toBeTruthy();
    expect(
      within(card).getByText("2.00 KiB/s", { selector: "div" }),
    ).toBeTruthy();
    expect(within(card).getByText("↑ 1.00 KiB/s upload")).toBeTruthy();
    // Cumulative counters must never be presented as a rate or vice versa.
    expect(card.textContent).not.toMatch(/cumulative/i);
    const summary = within(card).getByText("View 2 recent samples");
    summary.focus();
    await user.keyboard("{Enter}");
    const table = within(card).getByRole("table");
    expect(
      within(table).getByRole("columnheader", { name: "Transmit (B/s)" }),
    ).toBeTruthy();
    expect(within(table).getByText("1.00 KiB/s")).toBeTruthy();
    // The first sample has no predecessor, so it is shown as unavailable
    // instead of a fabricated zero rate.
    expect(within(table).getAllByText("Unavailable")).toHaveLength(2);
  });

  it("shows only the supplied filesystem and honest process and sensor panels", () => {
    seed();
    render(<OverviewPage />);
    const storage = screen.getByRole("article", { name: "Storage metric" });
    expect(
      within(storage).getByText("/test-volume · 40.00 GiB / 100.00 GiB used"),
    ).toBeTruthy();
    expect(within(storage).getAllByRole("progressbar")).toHaveLength(1);
    const processes = screen.getByRole("region", { name: "Running processes" });
    expect(processes.textContent).toContain("not provided");
    expect(within(processes).queryByRole("table")).toBeNull();
    expect(
      screen.getByRole("region", { name: "Temperature" }).textContent,
    ).toContain("not supplied");
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByText(/°C/)).toBeNull();
  });

  it("renders the process table when the snapshot supplies the group", () => {
    seed();
    useDashboardStore.getState().ingestSnapshot({
      seq: 3,
      ts: 3000,
      groups: {
        processes: {
          status: "ok",
          partial: false,
          value: {
            items: [
              {
                pid: 42,
                name: "worker",
                cpu_percent: 12.34,
                memory_rss_bytes: 5 * 1024 ** 2,
              },
            ],
            skipped: 0,
            total: 1,
          },
        },
      },
    });
    render(<OverviewPage />);
    const processes = screen.getByRole("region", { name: "Running processes" });
    const table = within(processes).getByRole("table", {
      name: /running processes/i,
    });
    expect(within(table).getByRole("rowheader", { name: "worker" })).toBeTruthy();
    expect(within(table).getByText("12.3%")).toBeTruthy();
    expect(within(table).getByText("5.00 MiB")).toBeTruthy();
    expect(within(table).getByText("42")).toBeTruthy();
  });

  it("hides old history when a metric becomes unavailable", () => {
    seed();
    render(<OverviewPage />);
    act(() =>
      useDashboardStore.getState().ingestSnapshot({
        seq: 3,
        ts: 3000,
        groups: {
          cpu: {
            status: "unavailable",
            kind: "permission",
            reason: "CPU counters unreadable",
          },
        },
      }),
    );
    const cpu = within(screen.getByRole("article", { name: "CPU metric" }));
    expect(cpu.getByText("CPU counters unreadable")).toBeTruthy();
    expect(cpu.queryByRole("img")).toBeNull();
    expect(cpu.queryByRole("progressbar")).toBeNull();
  });

  it.each(["stale", "disconnected", "fatal", "connecting"] as const)(
    "marks retained readings as not live when %s",
    (state) => {
      seed();
      useDashboardStore.getState().setConnectionState(state);
      render(<OverviewPage />);
      const cpu = within(screen.getByRole("article", { name: "CPU metric" }));
      expect(cpu.getByText("28.0%", { selector: "div" })).toBeTruthy();
      expect(cpu.getByText("Retained reading · not live")).toBeTruthy();
    },
  );
});
