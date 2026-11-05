import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "../../../src/presentation/components/MetricCard";
import { toLoading, toPartial, toUnavailable } from "../../../src/domain/metricState";
import { toStale } from "../../../src/domain/metricState";

describe("MetricCard", () => {
  it("renders loading", () => {
    render(<MetricCard title="CPU" metricState={toLoading()} value={null} />);
    expect(screen.getByText("Loading")).toBeTruthy();
  });
  it("renders unavailable with reason", () => {
    render(<MetricCard title="CPU" metricState={toUnavailable("permission", "proc denied")} value={null} />);
    expect(screen.getByText(/proc denied/i)).toBeTruthy();
  });
  it("renders numeric value", () => {
    render(<MetricCard title="CPU" metricState={{ status: "ok", value: 50 } as never} value={50} unit="%" />);
    expect(screen.getByText(/50/)).toBeTruthy();
  });
  it("renders stale", () => {
    render(<MetricCard title="CPU" metricState={toStale(60)} value={60} unit="%" />);
    expect(screen.getByText(/60/)).toBeTruthy();
  });
  it("renders unavailable with reason and no progressbar", () => {
    render(<MetricCard title="CPU" metricState={toUnavailable("permission", "proc denied")} value={null} unit="%" />);
    expect(screen.getByText(/proc denied/i)).toBeTruthy();
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
  it("has article role and aria-label", () => {
    render(<MetricCard title="CPU" metricState={toLoading()} value={null} />);
    expect(screen.getByRole("article", { name: /CPU metric/i })).toBeTruthy();
  });

  describe("percentage metrics keep the threshold indicator", () => {
    it("shows the gauge and the severity label", () => {
      render(
        <MetricCard title="CPU" unit="%" metricState={{ status: "ok", value: 97 }} value={97} />,
      );
      expect(screen.getByRole("progressbar", { name: /CPU usage/i })).toBeTruthy();
      expect(screen.getByText("Critical")).toBeTruthy();
    });

    it("shows Normal below the warning threshold", () => {
      render(
        <MetricCard title="Memory" unit="%" metricState={{ status: "ok", value: 42 }} value={42} />,
      );
      expect(screen.getByText("Normal")).toBeTruthy();
    });
  });

  describe("byte metrics are not treated as a percentage", () => {
    it("shows the byte value and detail without a gauge or severity label", () => {
      render(
        <MetricCard
          title="Network"
          unit="B"
          metricState={{ status: "ok", value: 1500000 }}
          value={1500000}
          detail="tx 1.20 MiB"
        />,
      );
      expect(screen.getByText("1.43 MiB")).toBeTruthy();
      expect(screen.getByText("tx 1.20 MiB")).toBeTruthy();
      // Byte counters have no agreed thresholds: no 0-100 bar, no severity.
      expect(screen.queryByRole("progressbar")).toBeNull();
      expect(screen.queryByText(/Normal|High|Critical/)).toBeNull();
    });

    it("never labels a large byte counter as Critical", () => {
      render(
        <MetricCard title="Network" unit="B" metricState={{ status: "ok", value: 5_000_000_000 }} value={5_000_000_000} />,
      );
      expect(screen.queryByText(/Critical/)).toBeNull();
      expect(screen.queryByRole("progressbar")).toBeNull();
    });
  });

  describe("partial state", () => {
    it("shows the partial badge exactly once with the info treatment", () => {
      render(
        <MetricCard
          title="CPU"
          unit="%"
          metricState={toPartial(12, "per-core counters unreadable")}
          value={12}
        />,
      );
      const badges = screen.getAllByText(/partial data/i);
      expect(badges).toHaveLength(1);
      const badge = badges[0]!;
      expect(badge.className).toContain("text-info");
      expect(badge.className).not.toContain("text-warn");
      expect(badge.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
      // The reason stays reachable: tooltip for pointer users, sr-only text for
      // assistive technology.
      expect(badge.getAttribute("title")).toBe("Partial data: per-core counters unreadable");
      expect(badge.textContent).toContain("per-core counters unreadable");
    });

    it("still shows the value and the percentage gauge while partial", () => {
      render(<MetricCard title="CPU" unit="%" metricState={toPartial(12)} value={12} />);
      expect(screen.getByText("12.0%")).toBeTruthy();
      expect(screen.getByRole("progressbar")).toBeTruthy();
      expect(screen.getAllByText(/partial data/i)).toHaveLength(1);
    });
  });
});

describe("metric history state gating", () => {
  it.each([
    { status: "loading" } as const,
    { status: "unavailable", kind: "unsupported", reason: "Not supported" } as const,
    { status: "error", error: "Reading failed" } as const,
  ])("does not expose a retained value, gauge or history for $status", (metricState) => {
    render(<MetricCard title="CPU" unit="%" metricState={metricState} value={42}><div>History content</div></MetricCard>);
    expect(screen.queryByText("42.0%")).toBeNull();
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByText("History content")).toBeNull();
  });

  it("labels a disconnected retained value and preserves its history", () => {
    render(<MetricCard title="CPU" unit="%" metricState={{ status: "disconnected" }} value={42}><div>History content</div></MetricCard>);
    expect(screen.getByText("Disconnected")).toBeTruthy();
    expect(screen.getByText("42.0%")).toBeTruthy();
    expect(screen.getByText("History content")).toBeTruthy();
  });
});
