import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sparkline } from "../../../src/presentation/components/Sparkline";

describe("Sparkline", () => {
  beforeEach(() => {
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
  afterEach(() => vi.restoreAllMocks());

  it("labels absent history instead of rendering an empty chart", () => {
    render(
      <Sparkline
        title="CPU"
        unit="%"
        series={[{ label: "CPU", token: "1", data: [null] }]}
      />,
    );
    expect(screen.getByText("History unavailable")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("shows gaps and measured zero distinctly in the chart and accessible table", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <Sparkline
        title="CPU"
        unit="%"
        series={[{ label: "CPU", token: "1", data: [10, 20, null, 0] }]}
      />,
    );
    const path =
      container.querySelector("path.recharts-line-curve")?.getAttribute("d") ??
      "";
    expect([...path.matchAll(/M/g)]).toHaveLength(2);
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain(
      "0–100% scale",
    );
    await user.click(screen.getByText("View 4 recent samples"));
    const table = within(screen.getByRole("table"));
    expect(table.getByText("Unavailable")).toBeTruthy();
    expect(table.getByText("0.0%")).toBeTruthy();
  });

  it("limits the text alternative and rendered series to the same 60 samples", async () => {
    const user = userEvent.setup();
    const data = Array.from({ length: 80 }, (_, i) => i);
    render(
      <Sparkline
        title="CPU"
        unit="%"
        series={[{ label: "CPU", token: "1", data }]}
      />,
    );
    await user.click(screen.getByText("View 60 recent samples"));
    const table = within(screen.getByRole("table"));
    expect(table.getAllByRole("row")).toHaveLength(61);
    expect(table.queryByText("19.0%")).toBeNull();
    expect(table.getByText("20.0%")).toBeTruthy();
    expect(table.getByText("79.0%")).toBeTruthy();
  });

  it("distinguishes counter directions by stroke pattern and labels", () => {
    const { container } = render(
      <Sparkline
        title="Network"
        unit="B"
        series={[
          { label: "Receive", token: "4", data: [1024, 2048] },
          { label: "Transmit", token: "2", data: [512, 1024] },
        ]}
      />,
    );
    const paths = container.querySelectorAll("path.recharts-line-curve");
    expect(paths).toHaveLength(2);
    expect(paths[0]?.getAttribute("stroke-dasharray")).toBeNull();
    expect(paths[1]?.getAttribute("stroke-dasharray")).toBe("4 3");
    expect(
      screen.getByText("Receive — solid · Transmit — dashed"),
    ).toBeTruthy();
    expect(screen.getByRole("img").getAttribute("aria-label")).toContain(
      "cumulative bytes",
    );
  });
});
