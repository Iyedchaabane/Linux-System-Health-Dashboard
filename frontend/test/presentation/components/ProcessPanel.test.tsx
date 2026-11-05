import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { ProcessPanel } from "../../../src/presentation/components/ProcessPanel";
import { useDashboardStore } from "../../../src/application/store";
import type { ConnectionStatus, ProcessList } from "../../../src/domain/types";

function ingestOk(value: ProcessList, partial = false, seq = 1) {
  useDashboardStore.getState().ingestSnapshot({
    seq,
    ts: seq,
    groups: {
      processes: { status: "ok", partial, value },
    },
  });
  useDashboardStore.getState().setConnectionState("open");
}

function ingestUnavailable(
  kind: "unsupported" | "permission" | "transient" | "disabled",
  reason: string,
) {
  useDashboardStore.getState().ingestSnapshot({
    seq: 1,
    ts: 1,
    groups: { processes: { status: "unavailable", kind, reason } },
  });
  useDashboardStore.getState().setConnectionState("open");
}

function setProcessState(
  state: ReturnType<typeof useDashboardStore.getState>["metricStates"]["processes"],
) {
  useDashboardStore.setState((s) => ({
    metricStates: { ...s.metricStates, processes: state },
  }));
}

const sampleItems: ProcessList["items"] = [
  { pid: 300, name: "zeta", cpu_percent: null, memory_rss_bytes: 5 * 1024 ** 2 },
  {
    pid: 100,
    name: "alpha",
    cpu_percent: 250,
    memory_rss_bytes: 2 * 1024 ** 3,
  },
  { pid: 200, name: "beta", cpu_percent: 12.34, memory_rss_bytes: 1024 ** 3 },
];

describe("ProcessPanel", () => {
  beforeEach(() => {
    useDashboardStore.getState().reset();
  });

  it("shows an honest loading state without rows", () => {
    render(<ProcessPanel />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading process data");
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryAllByRole("rowheader")).toHaveLength(0);
  });

  it("renders the server order exactly, without re-sorting or padding", () => {
    ingestOk({ items: sampleItems, skipped: 0 });
    render(<ProcessPanel />);
    const table = screen.getByRole("table", { name: /running processes/i });
    const rowHeaders = within(table).getAllByRole("rowheader");
    expect(rowHeaders.map((cell) => cell.textContent)).toEqual([
      "zeta",
      "alpha",
      "beta",
    ]);
    expect(rowHeaders).toHaveLength(sampleItems.length);
  });

  it("renders every received row in exact server order, without truncating or re-sorting", () => {
    // N > the 25-row default top-N: the server's top-N is configurable up to
    // 100, so the client must not silently drop rows a contract-compliant
    // server sends. Pids descend (1000, 999, ...), so server order is neither
    // name-sorted ("proc-10" sorts before "proc-2") nor pid-ascending.
    const rowCount = 30;
    const many: ProcessList["items"] = Array.from({ length: rowCount }, (_, i) => ({
      pid: 1000 - i,
      name: `proc-${i}`,
      cpu_percent: i,
      memory_rss_bytes: 1024,
    }));
    ingestOk({ items: many, skipped: 0 });
    render(<ProcessPanel />);
    const table = screen.getByRole("table", { name: /running processes/i });
    const rowHeaders = within(table).getAllByRole("rowheader");
    // Exactly N rows: no client-side truncation and no padding.
    expect(rowHeaders).toHaveLength(rowCount);
    // Exact server order, byte for byte: no re-sort, no invented rows.
    expect(rowHeaders.map((cell) => cell.textContent)).toEqual(
      Array.from({ length: rowCount }, (_, i) => `proc-${i}`),
    );
  });

  it("formats CPU and memory without clamping or inventing values", () => {
    ingestOk({ items: sampleItems, skipped: 0 });
    render(<ProcessPanel />);
    const table = screen.getByRole("table", { name: /running processes/i });
    expect(within(table).getByText("Measuring")).toBeTruthy();
    expect(within(table).getByText("250.0%")).toBeTruthy();
    expect(within(table).getByText("12.3%")).toBeTruthy();
    expect(within(table).getByText("5.00 MiB")).toBeTruthy();
    expect(within(table).getByText("2.00 GiB")).toBeTruthy();
    expect(within(table).getByText("1.00 GiB")).toBeTruthy();
    expect(within(table).getByText("300")).toBeTruthy();
  });

  it("truncates long names but exposes the full value in a title", () => {
    const longName = "x".repeat(128);
    ingestOk({
      items: [
        { pid: 9, name: longName, cpu_percent: 0, memory_rss_bytes: 0 },
      ],
      skipped: 0,
    });
    render(<ProcessPanel />);
    const rowHeader = screen.getByRole("rowheader");
    expect(rowHeader).toHaveTextContent(longName);
    expect(rowHeader).toHaveAttribute("title", longName);
  });

  it("labels an empty name only for display without mutating stored names or row values", () => {
    const actualName = "e\u0301😀";
    const value: ProcessList = {
      items: [
        { pid: 71, name: "", cpu_percent: null, memory_rss_bytes: 1024 },
        { pid: 72, name: actualName, cpu_percent: 3, memory_rss_bytes: 2048 },
      ],
      skipped: 0,
    };
    ingestOk(value);
    const before = useDashboardStore.getState();
    render(<ProcessPanel />);
    const unnamed = screen.getByRole("rowheader", { name: "Unnamed process" });
    expect(unnamed).toHaveAttribute("title", "Unnamed process");
    const named = screen.getByRole("rowheader", { name: actualName });
    expect(named.textContent).toBe(actualName);
    expect(named).toHaveAttribute("title", actualName);
    expect(screen.getAllByRole("rowheader")).toHaveLength(2);
    const unnamedRow = within(unnamed.closest("tr")!);
    expect(unnamedRow.getByText("71")).toBeTruthy();
    expect(unnamedRow.getByText("1.00 KiB")).toBeTruthy();
    expect(unnamedRow.getByText("Measuring")).toBeTruthy();
    expect(useDashboardStore.getState()).toBe(before);
    expect(before.metricStates.processes).toEqual({ status: "ok", value });
    expect(before.latestSnapshot?.groups.processes).toEqual({ status: "ok", partial: false, value });
    expect(value.items.map((item) => item.name)).toEqual(["", actualName]);
  });

  it("shows a partial indicator and the skipped count without color alone", () => {
    ingestOk(
      {
        items: [sampleItems[0]],
        skipped: 3,
      },
      true,
    );
    render(<ProcessPanel />);
    expect(screen.getByText("Partial data")).toBeTruthy();
    expect(screen.getByText("3 processes could not be read.")).toBeTruthy();
    expect(screen.getByRole("table")).toBeTruthy();
  });

  it("explains partial data when no processes were skipped", () => {
    ingestOk({ items: [sampleItems[0]], skipped: 0 }, true);
    render(<ProcessPanel />);
    expect(screen.getByText("Partial data")).toBeTruthy();
    expect(
      screen.getByText("Some CPU values are not measured yet."),
    ).toBeTruthy();
  });

  it("shows skipped information for an ok list", () => {
    ingestOk({ items: [sampleItems[0]], skipped: 2 });
    render(<ProcessPanel />);
    expect(screen.getByText("2 processes could not be read.")).toBeTruthy();
    expect(screen.queryByText("Partial data")).toBeNull();
  });

  it("shows the unavailable kind and reason without a table", () => {
    ingestUnavailable("permission", "Process listing is not permitted");
    render(<ProcessPanel />);
    expect(screen.getByText("Needs permission")).toBeTruthy();
    expect(
      screen.getByText("Process listing is not permitted"),
    ).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("explains an absent group without fabricating an unavailable kind", () => {
    useDashboardStore.getState().ingestSnapshot({
      seq: 1,
      ts: 1,
      groups: {
        cpu: { status: "ok", partial: false, value: { cpu_total: 1 } },
      },
    });
    useDashboardStore.getState().setConnectionState("open");
    render(<ProcessPanel />);
    const panel = screen.getByRole("region", { name: "Running processes" });
    // The honest label appears exactly twice: the header status badge and the
    // message title. Neither may claim a wire unavailable kind.
    expect(within(panel).getAllByText("Not provided")).toHaveLength(2);
    expect(within(panel).getByText(/not provided by the server/i)).toBeTruthy();
    expect(screen.queryByText("Not supported on this host")).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("reports an ok empty list as no processes, not an error", () => {
    ingestOk({ items: [], skipped: 0 });
    render(<ProcessPanel />);
    expect(
      screen.getByText("No processes reported in the latest snapshot."),
    ).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByText("Error")).toBeNull();
  });

  it.each([
    ["stale", "Stale · retained reading"],
    ["disconnected", "Disconnected · showing last received list"],
    ["fatal", "Disconnected · showing last received list"],
    ["connecting", "Reconnecting · showing last received list"],
  ] as const)("keeps the last list and marks it when %s", (connection, label) => {
    ingestOk({ items: sampleItems, skipped: 0 });
    useDashboardStore.getState().setConnectionState(connection as ConnectionStatus);
    render(<ProcessPanel />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByRole("rowheader", { name: "zeta" })).toBeTruthy();
  });

  it("shows an informative error state", () => {
    setProcessState({
      status: "error",
      error: "collector failed",
      message: "The process collector failed.",
    });
    render(<ProcessPanel />);
    expect(screen.getByText("The process collector failed.")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("exposes table semantics and all four column headers", () => {
    ingestOk({ items: sampleItems, skipped: 0 });
    render(<ProcessPanel />);
    const panel = screen.getByRole("region", { name: "Running processes" });
    const table = within(panel).getByRole("table", {
      name: /running processes/i,
    });
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((header) => header.textContent)).toEqual([
      "Name",
      "CPU",
      "Memory (RSS)",
      "PID",
    ]);
    for (const header of headers) {
      expect(header).toHaveAttribute("scope", "col");
    }
    const rowHeaders = within(table).getAllByRole("rowheader");
    expect(rowHeaders).toHaveLength(sampleItems.length);
    for (const rowHeader of rowHeaders) {
      expect(rowHeader).toHaveAttribute("scope", "row");
    }
  });
});
