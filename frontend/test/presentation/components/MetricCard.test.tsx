import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "../../../src/presentation/components/MetricCard";
import { toLoading, toUnavailable } from "../../../src/domain/metricState";
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
});
