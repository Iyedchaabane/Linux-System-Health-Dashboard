/**
 * Contract regression tests for the shared `processes` group fixtures.
 *
 * The 14 fixtures in `contracts/ws/v1/fixtures/processes/` cover the shape of the
 * `processes` snapshot group only. They carry the real `data.type: "snapshot"`
 * discriminator, which the published static schema now requires, so real server
 * output validates against the published schema.
 *
 * These are the same files the backend validates with Pydantic and the published
 * JSON Schema, so both sides must reach the same verdict per fixture.
 */
import { describe, expect, it } from "vitest";

import invalidProcessesName129 from "../../../contracts/ws/v1/fixtures/processes/invalid_processes_name_129.json";
import invalidProcessesNegativeCpu from "../../../contracts/ws/v1/fixtures/processes/invalid_processes_negative_cpu.json";
import invalidProcessesNegativeRss from "../../../contracts/ws/v1/fixtures/processes/invalid_processes_negative_rss.json";
import invalidProcessesNegativeSkipped from "../../../contracts/ws/v1/fixtures/processes/invalid_processes_negative_skipped.json";
import invalidProcessesPidZero from "../../../contracts/ws/v1/fixtures/processes/invalid_processes_pid_zero.json";
import invalidProcessesWrongNameType from "../../../contracts/ws/v1/fixtures/processes/invalid_processes_wrong_name_type.json";
import invalidProcessesWrongPidType from "../../../contracts/ws/v1/fixtures/processes/invalid_processes_wrong_pid_type.json";
import validProcessesCpuOver100 from "../../../contracts/ws/v1/fixtures/processes/valid_processes_cpu_over_100.json";
import validProcessesEmptyList from "../../../contracts/ws/v1/fixtures/processes/valid_processes_empty_list.json";
import validProcessesEmptyName from "../../../contracts/ws/v1/fixtures/processes/valid_processes_empty_name.json";
import validProcessesName128Codepoints from "../../../contracts/ws/v1/fixtures/processes/valid_processes_name_128_codepoints.json";
import validProcessesNormal from "../../../contracts/ws/v1/fixtures/processes/valid_processes_normal.json";
import validProcessesNullCpu from "../../../contracts/ws/v1/fixtures/processes/valid_processes_null_cpu.json";
import validProcessesPartialSkipped from "../../../contracts/ws/v1/fixtures/processes/valid_processes_partial_skipped.json";

import { parseServerMessage } from "../../src/infrastructure/ws/schemas";

type Fixture = { name: string; payload: unknown; valid: boolean };

const fixtures: Fixture[] = [
  { name: "invalid_processes_name_129.json", payload: invalidProcessesName129, valid: false },
  { name: "invalid_processes_negative_cpu.json", payload: invalidProcessesNegativeCpu, valid: false },
  { name: "invalid_processes_negative_rss.json", payload: invalidProcessesNegativeRss, valid: false },
  {
    name: "invalid_processes_negative_skipped.json",
    payload: invalidProcessesNegativeSkipped,
    valid: false,
  },
  { name: "invalid_processes_pid_zero.json", payload: invalidProcessesPidZero, valid: false },
  {
    name: "invalid_processes_wrong_name_type.json",
    payload: invalidProcessesWrongNameType,
    valid: false,
  },
  {
    name: "invalid_processes_wrong_pid_type.json",
    payload: invalidProcessesWrongPidType,
    valid: false,
  },
  { name: "valid_processes_cpu_over_100.json", payload: validProcessesCpuOver100, valid: true },
  { name: "valid_processes_empty_list.json", payload: validProcessesEmptyList, valid: true },
  { name: "valid_processes_empty_name.json", payload: validProcessesEmptyName, valid: true },
  {
    name: "valid_processes_name_128_codepoints.json",
    payload: validProcessesName128Codepoints,
    valid: true,
  },
  { name: "valid_processes_normal.json", payload: validProcessesNormal, valid: true },
  { name: "valid_processes_null_cpu.json", payload: validProcessesNullCpu, valid: true },
  {
    name: "valid_processes_partial_skipped.json",
    payload: validProcessesPartialSkipped,
    valid: true,
  },
];

type ProcessesPayload = {
  data: { groups: { processes: { value: { items: Array<{ name: string }> } } } };
};

/** The longest process name in a fixture, i.e. the one near the 128 limit. */
function longestProcessName(payload: unknown): string {
  const typed = payload as ProcessesPayload;
  const names = typed.data.groups.processes.value.items.map((item) => item.name);
  return names.sort((a, b) => Array.from(b).length - Array.from(a).length)[0];
}

describe("process contract fixtures (shared with the backend)", () => {
  it("imports exactly the approved 14 fixtures, 7 accepted and 7 rejected", () => {
    expect(fixtures).toHaveLength(14);
    expect(fixtures.filter((fixture) => fixture.valid)).toHaveLength(7);
    expect(fixtures.filter((fixture) => !fixture.valid)).toHaveLength(7);
    expect(new Set(fixtures.map((fixture) => fixture.name)).size).toBe(14);
  });

  it.each(fixtures)("$name -> valid=$valid", ({ payload, valid }) => {
    if (valid) {
      expect(() => parseServerMessage(payload)).not.toThrow();
    } else {
      expect(() => parseServerMessage(payload)).toThrow();
    }
  });

  it("counts the 128 name limit in Unicode code points, not UTF-16 units", () => {
    const accepted = longestProcessName(validProcessesName128Codepoints);
    const rejected = longestProcessName(invalidProcessesName129);

    expect(Array.from(accepted)).toHaveLength(128);
    expect(accepted.length).toBeGreaterThan(128);
    expect(Array.from(rejected)).toHaveLength(129);
  });
});
