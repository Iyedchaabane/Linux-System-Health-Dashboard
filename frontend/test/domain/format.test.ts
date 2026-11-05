import { describe, expect, it } from "vitest";
import { formatBytes, formatPercent, formatRate } from "../../src/domain/format";

describe("formatPercent", () => {
  it("formats finite number", () => expect(formatPercent(50)).toBe("50.0%"));
  it("handles null/undefined/NaN/Infinity", () => {
    expect(formatPercent(null)).toBe("--");
    expect(formatPercent(undefined)).toBe("--");
    expect(formatPercent(NaN)).toBe("--");
    expect(formatPercent(Infinity)).toBe("--");
  });
  it("formats 0", () => expect(formatPercent(0)).toBe("0.0%"));
});

describe("formatBytes", () => {
  it("formats 0", () => expect(formatBytes(0)).toBe("0 B"));
  it("handles null/undefined/NaN", () => {
    expect(formatBytes(null)).toBe("--");
    expect(formatBytes(undefined)).toBe("--");
    expect(formatBytes(NaN)).toBe("--");
  });
  it("formats bytes", () => expect(formatBytes(512)).toBe("512 B"));
  it("formats KiB", () => expect(formatBytes(1024)).toBe("1.00 KiB"));
  it("formats GiB", () => expect(formatBytes(1024 ** 3)).toBe("1.00 GiB"));
  it("negative values", () => expect(formatBytes(-1024)).toBe("-1.00 KiB"));
});
describe("formatRate", () => {
  it("appends a per-second unit to the byte magnitude", () => {
    expect(formatRate(1024)).toBe("1.00 KiB/s");
    expect(formatRate(1_200_000)).toBe("1.14 MiB/s");
  });
  it("formats zero as 0 B/s", () => expect(formatRate(0)).toBe("0 B/s"));
  it("returns -- when no rate exists", () => {
    expect(formatRate(null)).toBe("--");
    expect(formatRate(undefined)).toBe("--");
    expect(formatRate(Number.NaN)).toBe("--");
    expect(formatRate(Number.POSITIVE_INFINITY)).toBe("--");
  });
});
