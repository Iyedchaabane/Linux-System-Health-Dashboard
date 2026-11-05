import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TimeSeriesChart } from "../../../src/presentation/components/TimeSeriesChart";

// Recharts measures its parent through ResizeObserver/getBoundingClientRect and
// renders nothing for a zero-size box, which is what jsdom reports by default.
// Give it a deterministic 500x200 viewport so the SVG output can be asserted.
// The default 5px chart margin leaves a 190px-tall plot area (y from 5 to 195).
const VIEWPORT = { width: 500, height: 200 };

function useFixedViewport(): void {
  Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
    configurable: true,
    value: () => ({
      ...VIEWPORT,
      top: 0,
      left: 0,
      right: VIEWPORT.width,
      bottom: VIEWPORT.height,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    }),
  });
}

function renderedYs(container: HTMLElement): number[] {
  const path = container.querySelector("path.recharts-line-curve");
  const d = path?.getAttribute("d") ?? "";
  return [...d.matchAll(/[ML]([\d.]+),([\d.]+)/g)].map((match) => Number(match[2]));
}

describe("TimeSeriesChart", () => {
  beforeEach(useFixedViewport);

  it("renders empty state", () => {
    render(<TimeSeriesChart title="CPU" data={[]} />);
    expect(screen.getByText(/Waiting for data/i)).toBeTruthy();
  });

  it("bounds history to 60 points", () => {
    const data = Array.from({ length: 100 }, (_, i) => i);
    const { container } = render(<TimeSeriesChart title="CPU usage" unit="%" data={data} />);
    expect(screen.getByText(/Latest 99%/)).toBeTruthy();
    const d = container.querySelector("path.recharts-line-curve")?.getAttribute("d") ?? "";
    // 60 rendered samples: one move plus one cubic segment per following point.
    expect([...d.matchAll(/M/g)]).toHaveLength(1);
    expect([...d.matchAll(/C/g)]).toHaveLength(59);
    // The window starts at sample 40 (y=119 on a 0-100 domain), not at sample 0.
    expect(renderedYs(container)[0]).toBeCloseTo(119, 0);
    expect(screen.getByText(/Chart showing CPU usage over time/).textContent).toContain(
      "Latest value 99",
    );
  });

  it("defaults a percentage series to a fixed 0-100 domain", () => {
    const { container } = render(<TimeSeriesChart title="CPU usage" unit="%" data={[50, 50]} />);
    expect(container.firstElementChild?.getAttribute("data-domain")).toBe("0,100");
    // A 50% sample sits at the vertical midpoint of the plot area. With an
    // auto-scaled domain it would be pinned to the top instead.
    expect(renderedYs(container)).toEqual([100, 100]);
  });

  it("honours an explicit domain prop", () => {
    const { container } = render(
      <TimeSeriesChart title="CPU usage" unit="%" data={[25, 25]} domain={[0, 50]} />,
    );
    expect(container.firstElementChild?.getAttribute("data-domain")).toBe("0,50");
    expect(renderedYs(container)).toEqual([100, 100]);
  });

  it("does not force a 0-100 domain on byte series", () => {
    const { container } = render(
      <TimeSeriesChart title="Network rx" unit="B" data={[1000, 3000]} />,
    );
    expect(container.firstElementChild?.getAttribute("data-domain")).not.toBe("0,100");
    const ys = renderedYs(container);
    expect(ys).toHaveLength(2);
    // Auto-scaled to the samples: the largest is at the top, the smaller one is
    // still mid-chart. A 0-100 percentage domain would clamp both to the top.
    expect(Math.min(...ys)).toBeCloseTo(5, 0);
    expect(Math.max(...ys)).toBeGreaterThan(100);
  });

  it("accepts null samples and renders them as gaps", () => {
    const { container } = render(
      <TimeSeriesChart title="CPU usage" unit="%" data={[10, 20, null, 40]} />,
    );
    const path = container.querySelector("path.recharts-line-curve");
    const d = path?.getAttribute("d") ?? "";
    // Two subpaths: the null sample breaks the line instead of being joined
    // (connectNulls={false}) or plotted as 0.
    expect([...d.matchAll(/M/g)]).toHaveLength(2);
    expect(renderedYs(container)).toHaveLength(3);
    expect(screen.getByText(/Latest 40%/)).toBeTruthy();
  });

  it("strokes the line with the chart-1 token", () => {
    const { container } = render(<TimeSeriesChart title="CPU usage" unit="%" data={[10, 20]} />);
    const path = container.querySelector("path.recharts-line-curve");
    expect(path?.getAttribute("stroke")).toBe("rgb(var(--chart-1))");
  });

  it("chart aria-label", () => {
    render(<TimeSeriesChart title="CPU" data={[]} />);
    expect(screen.getByRole("img", { name: /CPU chart/i })).toBeTruthy();
  });
});
