/**
 * Derive transfer rates from cumulative network byte counters.
 *
 * The backend sends cumulative counters (`rx_bytes`/`tx_bytes`) because that is
 * what the kernel exposes. A rate is only meaningful as a difference between
 * two consecutive samples divided by the monotonic time that elapsed between
 * them; cumulative totals are never presented as bytes per second.
 */

/** One cumulative counter reading plus the monotonic time it was received. */
export type NetworkCountersSample = {
  /** Cumulative received bytes since boot. */
  rxBytes: number;
  /** Cumulative transmitted bytes since boot. */
  txBytes: number;
  /** Monotonic receipt time in milliseconds (`performance.now()`). */
  at: number;
};

export type NetworkRates = {
  rxBytesPerSecond: number;
  txBytesPerSecond: number;
};

/** Sub-millisecond intervals produce meaningless spikes, so they are rejected. */
const MIN_INTERVAL_MS = 1;

/** A counter reading is usable only when both totals are finite and non-negative. */
export function isValidCounters(value: {
  rx_bytes?: unknown;
  tx_bytes?: unknown;
} | null | undefined): value is { rx_bytes: number; tx_bytes: number } {
  if (!value) return false;
  const { rx_bytes: rx, tx_bytes: tx } = value;
  return (
    typeof rx === "number" &&
    typeof tx === "number" &&
    Number.isFinite(rx) &&
    Number.isFinite(tx) &&
    rx >= 0 &&
    tx >= 0
  );
}

/**
 * Compute per-second rates between two cumulative samples.
 *
 * Returns `null` — never a fabricated zero — when a rate cannot be derived:
 * no previous sample (first reading), non-monotonic or invalid elapsed time, or
 * counters that went backwards (interface reset, driver reset, reboot).
 */
export function computeNetworkRates(
  previous: NetworkCountersSample | null,
  current: NetworkCountersSample | null,
): NetworkRates | null {
  if (!previous || !current) return null;

  const elapsedMs = current.at - previous.at;
  if (!Number.isFinite(elapsedMs) || elapsedMs < MIN_INTERVAL_MS) return null;

  const rxDelta = current.rxBytes - previous.rxBytes;
  const txDelta = current.txBytes - previous.txBytes;
  if (!Number.isFinite(rxDelta) || !Number.isFinite(txDelta)) return null;
  if (rxDelta < 0 || txDelta < 0) return null;

  const seconds = elapsedMs / 1000;
  return {
    rxBytesPerSecond: rxDelta / seconds,
    txBytesPerSecond: txDelta / seconds,
  };
}

/** Most recent non-null value of a bounded history series. */
export function latestRate(history: readonly (number | null)[]): number | null {
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const value = history[i];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}
