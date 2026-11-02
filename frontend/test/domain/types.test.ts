import { describe, expect, it } from "vitest";
import {
  METRIC_GROUPS,
  METRIC_STATES,
  PROTOCOL_VERSION,
} from "../../src/domain/types";

describe("domain types", () => {
  it("exposes protocol version 1", () => {
    expect(PROTOCOL_VERSION).toBe(1);
  });

  it("lists cpu and memory groups", () => {
    expect(METRIC_GROUPS).toEqual(["cpu", "memory", "disk", "network"]);
  });

  it("metric state list has 7 entries", () => {
    expect(METRIC_STATES).toHaveLength(7);
  });
});