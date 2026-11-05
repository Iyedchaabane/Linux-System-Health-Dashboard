/**
 * Pure display formatters for dashboard metrics.
 *
 * Numeric missing values render as "--"; formatting for tabular alignment
 * is provided by the `.tabular-nums` CSS class rather than by these helpers.
 */

const BYTE_UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"] as const;

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  return `${value.toFixed(1)}%`;
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "--";
  }
  if (value === 0) {
    return "0 B";
  }
  const exponent = Math.min(
    BYTE_UNITS.length - 1,
    Math.floor(Math.log2(Math.abs(value)) / 10),
  );
  const magnitude = value / 2 ** (exponent * 10);
  const decimals = exponent === 0 ? 0 : 2;
  return `${magnitude.toFixed(decimals)} ${BYTE_UNITS[exponent]}`;
}

/** Bytes per second, e.g. `1.14 MiB/s`; `--` when no rate can be derived. */
export function formatRate(bytesPerSecond: number | null | undefined): string {
  if (bytesPerSecond === null || bytesPerSecond === undefined || !Number.isFinite(bytesPerSecond)) {
    return "--";
  }
  return `${formatBytes(bytesPerSecond)}/s`;
}
