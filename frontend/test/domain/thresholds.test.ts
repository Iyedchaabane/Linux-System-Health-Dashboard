import { describe, expect, it } from "vitest";
import {
  DEFAULT_THRESHOLD_VALUES,
  DEFAULT_THRESHOLDS,
  defaultThresholds,
  isCritical,
  isWarning,
  mergeThresholds,
  severityFromValue,
} from "../../src/domain/thresholds";

describe("thresholds", () => {
  it("defaults to warn 80 and critical 95", () => {
    expect(DEFAULT_THRESHOLD_VALUES.warn).toBe(80);
    expect(DEFAULT_THRESHOLD_VALUES.critical).toBe(95);
    for (const key of ["cpu", "memory", "disk"] as const) {
      expect(DEFAULT_THRESHOLDS[key]).toEqual({ warn: 80, critical: 95 });
      expect(defaultThresholds(key)).toEqual({ warn: 80, critical: 95 });
    }
  });

  it("classifies values with defaults", () => {
    const t = DEFAULT_THRESHOLD_VALUES;
    expect(severityFromValue(50, t)).toBe("ok");
    expect(severityFromValue(80, t)).toBe("warning");
    expect(severityFromValue(95, t)).toBe("critical");
    expect(isWarning(85, t)).toBe(true);
    expect(isCritical(99, t)).toBe(true);
  });

  it("supports configurable overrides", () => {
    const merged = mergeThresholds(DEFAULT_THRESHOLD_VALUES, { warn: 70, critical: 90 });
    expect(merged).toEqual({ warn: 70, critical: 90 });
    expect(severityFromValue(75, merged)).toBe("warning");
  });
});