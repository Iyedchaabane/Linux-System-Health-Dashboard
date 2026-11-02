import { calculateBackoff, isFatalCode } from "../../src/infrastructure/ws/backoff";
import { describe, expect, it } from "vitest";

describe("calculateBackoff", () => {
  it("full jitter result stays within [0, capped]", () => {
    for (let i = 0; i < 100; i++) {
      const v = calculateBackoff({ baseMs: 1000, capMs: 30000, retryCount: 2, jitter: "full" });
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(30000);
    }
  });
  it("none jitter gives deterministic exponential", () => {
    expect(calculateBackoff({ baseMs: 1000, capMs: 30000, retryCount: 2, jitter: "none" })).toBe(4000);
    expect(calculateBackoff({ baseMs: 1000, capMs: 30000, retryCount: 10, jitter: "none" })).toBe(30000);
  });
});

describe("isFatalCode", () => {
  it("fatal codes", () => {
    expect(isFatalCode(1008)).toBe(true);
    expect(isFatalCode(4400)).toBe(true);
    expect(isFatalCode(4401)).toBe(true);
  });
  it("non-fatal codes", () => {
    expect(isFatalCode(1000)).toBe(false);
    expect(isFatalCode(1011)).toBe(false);
    expect(isFatalCode(4429)).toBe(false);
  });
});
