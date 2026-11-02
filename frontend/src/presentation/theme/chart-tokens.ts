export type ChartTokens = {
  1: string;
  2: string;
  3: string;
  4: string;
  5: string;
  6: string;
  neutral: string;
};

const FALLBACKS: ChartTokens = {
  1: "#0072B2",
  2: "#C2410C",
  3: "#00875F",
  4: "#A8467F",
  5: "#8A6D00",
  6: "#6D28D9",
  neutral: "#6B7280",
};

const CSS_VAR_BY_KEY: Record<keyof ChartTokens, string> = {
  1: "--chart-1",
  2: "--chart-2",
  3: "--chart-3",
  4: "--chart-4",
  5: "--chart-5",
  6: "--chart-6",
  neutral: "--chart-neutral",
};

const rgbFromVar = (value: string): string => {
  const parts = value.trim().split(/\s+/);
  if (parts.length === 3 && parts.every((p) => /^\d+(\.\d+)?$/.test(p))) {
    return `rgb(${parts.join(" ")})`;
  }
  return "";
};

export function readChartTokens(root: HTMLElement | null = typeof document !== "undefined" ? document.documentElement : null): ChartTokens {
  if (!root) return { ...FALLBACKS };
  const styles = getComputedStyle(root);
  const out = { ...FALLBACKS } as ChartTokens;
  (Object.keys(CSS_VAR_BY_KEY) as Array<keyof ChartTokens>).forEach((key) => {
    const raw = styles.getPropertyValue(CSS_VAR_BY_KEY[key]);
    const rgb = rgbFromVar(raw);
    if (rgb) out[key] = rgb;
  });
  return out;
}

export { FALLBACKS as chartTokenFallbacks };
