import { describe, expect, it } from "vitest";

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "").trim();
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return [
    parseInt(full.slice(0, 2), 16),
    parseInt(full.slice(2, 4), 16),
    parseInt(full.slice(4, 6), 16),
  ];
}

function luminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex).map((c) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(fg: string, bg: string): number {
  const l1 = luminance(fg);
  const l2 = luminance(bg);
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

type Pair = { name: string; fg: string; bg: string; min: number };

describe("design-system contrast", () => {
  const textPairs: Pair[] = [
    // light theme on bg
    { name: "light text/bg", fg: "#1C1917", bg: "#E5E4E2", min: 4.5 },
    { name: "light muted/bg", fg: "#57534E", bg: "#E5E4E2", min: 4.5 },
    { name: "light primary/bg", fg: "#6F4E37", bg: "#E5E4E2", min: 4.5 },
    { name: "light secondary/bg", fg: "#5B4B8A", bg: "#E5E4E2", min: 4.5 },
    { name: "light ok/bg", fg: "#166534", bg: "#E5E4E2", min: 4.5 },
    { name: "light warn/bg", fg: "#92400E", bg: "#E5E4E2", min: 4.5 },
    { name: "light critical/bg", fg: "#991B1B", bg: "#E5E4E2", min: 4.5 },
    // light theme on surface
    { name: "light text/surface", fg: "#1C1917", bg: "#F4F3F1", min: 4.5 },
    { name: "light muted/surface", fg: "#57534E", bg: "#F4F3F1", min: 4.5 },
    { name: "light primary/surface", fg: "#6F4E37", bg: "#F4F3F1", min: 4.5 },
    // dark theme on bg
    { name: "dark text/bg", fg: "#EDEDED", bg: "#0A0A0A", min: 4.5 },
    { name: "dark muted/bg", fg: "#A3A3A3", bg: "#0A0A0A", min: 4.5 },
    { name: "dark primary/bg", fg: "#3DB8E0", bg: "#0A0A0A", min: 4.5 },
    { name: "dark secondary/bg", fg: "#FF2D95", bg: "#0A0A0A", min: 4.5 },
    { name: "dark ok/bg", fg: "#4ADE80", bg: "#0A0A0A", min: 4.5 },
    { name: "dark warn/bg", fg: "#FBBF24", bg: "#0A0A0A", min: 4.5 },
    { name: "dark critical/bg", fg: "#F87171", bg: "#0A0A0A", min: 4.5 },
    // dark theme on surface
    { name: "dark text/surface", fg: "#EDEDED", bg: "#141414", min: 4.5 },
    { name: "dark muted/surface", fg: "#A3A3A3", bg: "#141414", min: 4.5 },
    { name: "dark primary/surface", fg: "#3DB8E0", bg: "#141414", min: 4.5 },
  ];

  it.each(textPairs)("$name >= $min:1", ({ fg, bg, min }) => {
    expect(ratio(fg, bg)).toBeGreaterThanOrEqual(min);
  });

  const uiPairs: Pair[] = [
    { name: "light border-strong/bg", fg: "#78716C", bg: "#E5E4E2", min: 3 },
    { name: "dark border-strong/bg", fg: "#737373", bg: "#0A0A0A", min: 3 },
    { name: "dark focus-ring/bg", fg: "#7DD3FC", bg: "#0A0A0A", min: 3 },
  ];
  it.each(uiPairs)("$name >= $min:1", ({ fg, bg, min }) => {
    expect(ratio(fg, bg)).toBeGreaterThanOrEqual(min);
  });

  const chartPairs: Pair[] = [
    // light charts on surface #F4F3F1
    { name: "light chart-1", fg: "#0072B2", bg: "#F4F3F1", min: 3 },
    { name: "light chart-2", fg: "#C2410C", bg: "#F4F3F1", min: 3 },
    { name: "light chart-3", fg: "#00875F", bg: "#F4F3F1", min: 3 },
    { name: "light chart-4", fg: "#A8467F", bg: "#F4F3F1", min: 3 },
    { name: "light chart-5", fg: "#8A6D00", bg: "#F4F3F1", min: 3 },
    { name: "light chart-6", fg: "#6D28D9", bg: "#F4F3F1", min: 3 },
    { name: "light chart-neutral", fg: "#6B7280", bg: "#F4F3F1", min: 3 },
    // dark charts on surface #141414
    { name: "dark chart-1", fg: "#38A9DB", bg: "#141414", min: 3 },
    { name: "dark chart-2", fg: "#E69F00", bg: "#141414", min: 3 },
    { name: "dark chart-3", fg: "#00B386", bg: "#141414", min: 3 },
    { name: "dark chart-4", fg: "#F0E442", bg: "#141414", min: 3 },
    { name: "dark chart-5", fg: "#CC79A7", bg: "#141414", min: 3 },
    { name: "dark chart-6", fg: "#E8743B", bg: "#141414", min: 3 },
    { name: "dark chart-neutral", fg: "#A3A3A3", bg: "#141414", min: 3 },
  ];
  it.each(chartPairs)("$name >= $min:1", ({ fg, bg, min }) => {
    expect(ratio(fg, bg)).toBeGreaterThanOrEqual(min);
  });

  it("button labels meet contrast on fills", () => {
    expect(ratio("#FFFFFF", "#6F4E37")).toBeGreaterThanOrEqual(4.5);
    expect(ratio("#FFFFFF", "#007BA7")).toBeGreaterThanOrEqual(4.5);
    expect(ratio("#0A0A0A", "#FF2D95")).toBeGreaterThanOrEqual(4.5);
  });
});
