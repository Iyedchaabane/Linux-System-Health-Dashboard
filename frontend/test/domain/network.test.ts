import { describe, expect, it } from "vitest";
import {
  computeNetworkRates,
  isValidCounters,
  latestRate,
  type NetworkCountersSample,
} from "../../src/domain/network";

const sample = (rxBytes: number, txBytes: number, at: number): NetworkCountersSample => ({
  rxBytes,
  txBytes,
  at,
});

describe("computeNetworkRates", () => {
  it("returns null for the first sample (no previous counters)", () => {
    expect(computeNetworkRates(null, sample(1000, 500, 0))).toBeNull();
    expect(computeNetworkRates(sample(1000, 500, 0), null)).toBeNull();
  });

  it("divides counter deltas by the monotonic elapsed time", () => {
    // 2 KiB received and 1 KiB sent over exactly one second.
    const rates = computeNetworkRates(sample(1000, 500, 0), sample(3048, 1524, 1000));
    expect(rates).not.toBeNull();
    expect(rates!.rxBytesPerSecond).toBeCloseTo(2048, 6);
    expect(rates!.txBytesPerSecond).toBeCloseTo(1024, 6);
  });

  it("uses the real interval, not an assumed one", () => {
    const rates = computeNetworkRates(sample(0, 0, 1000), sample(500, 250, 3000));
    expect(rates!.rxBytesPerSecond).toBeCloseTo(250, 6);
    expect(rates!.txBytesPerSecond).toBeCloseTo(125, 6);
  });

  it("never treats cumulative counters as a rate", () => {
    const rates = computeNetworkRates(sample(0, 0, 0), sample(1_000_000, 1_000_000, 1000));
    // 1 MB/s only because the delta over one second is 1 MB — not because the
    // counter itself is 1 MB.
    expect(rates!.rxBytesPerSecond).toBeCloseTo(1_000_000, 6);
    expect(rates!.rxBytesPerSecond).not.toBe(1_000_000_000);
  });

  it("returns null when the counters went backwards (reset)", () => {
    expect(computeNetworkRates(sample(5000, 5000, 0), sample(10, 5000, 1000))).toBeNull();
    expect(computeNetworkRates(sample(5000, 5000, 0), sample(5000, 10, 1000))).toBeNull();
  });

  it("returns null for zero, negative or non-finite intervals", () => {
    expect(computeNetworkRates(sample(0, 0, 1000), sample(100, 100, 1000))).toBeNull();
    expect(computeNetworkRates(sample(0, 0, 2000), sample(100, 100, 1000))).toBeNull();
    expect(computeNetworkRates(sample(0, 0, Number.NaN), sample(100, 100, 1000))).toBeNull();
  });

  it("returns null instead of NaN for non-finite counter values", () => {
    expect(computeNetworkRates(sample(0, 0, 0), sample(Number.POSITIVE_INFINITY, 0, 1000))).toBeNull();
  });
});

describe("isValidCounters", () => {
  it("accepts finite non-negative counters", () => {
    expect(isValidCounters({ rx_bytes: 0, tx_bytes: 12 })).toBe(true);
  });

  it("rejects missing, negative, non-numeric or non-finite counters", () => {
    expect(isValidCounters(null)).toBe(false);
    expect(isValidCounters({})).toBe(false);
    expect(isValidCounters({ rx_bytes: -1, tx_bytes: 0 })).toBe(false);
    expect(isValidCounters({ rx_bytes: "12", tx_bytes: 0 })).toBe(false);
    expect(isValidCounters({ rx_bytes: Number.NaN, tx_bytes: 0 })).toBe(false);
  });
});

describe("latestRate", () => {
  it("returns the most recent non-null value", () => {
    expect(latestRate([null, 100, 200, null])).toBe(200);
  });

  it("returns null for an empty or all-null history", () => {
    expect(latestRate([])).toBeNull();
    expect(latestRate([null, null])).toBeNull();
  });
});
