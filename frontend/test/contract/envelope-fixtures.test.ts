/**
 * Contract regression tests for the shared snapshot envelope fixtures.
 *
 * `contracts/ws/v1/fixtures/envelope/` holds a genuine backend
 * `serialize_snapshot` output plus mutated copies: one whose `data.type` is
 * `"pong"`, one with `data.type` removed, and a ping carrying snapshot-only
 * fields. The published schema requires `data.type: "snapshot"`, so the real
 * envelope must parse and the mutated copies must be rejected. The three
 * published root snapshot fixtures must parse too, since they no longer
 * contradict the published schema.
 *
 * JSON is imported statically: this project has no `@types/node`.
 */
import { describe, expect, it } from "vitest";

import invalidSnapshotEnvelopeDiscriminator from "../../../contracts/ws/v1/fixtures/envelope/invalid_snapshot_envelope_discriminator.json";
import invalidSnapshotEnvelopeMissingDiscriminator from "../../../contracts/ws/v1/fixtures/envelope/invalid_snapshot_envelope_missing_discriminator.json";
import invalidPingWithSnapshotFields from "../../../contracts/ws/v1/fixtures/envelope/invalid_ping_with_snapshot_fields.json";
import validPingEmptyData from "../../../contracts/ws/v1/fixtures/envelope/valid_ping_empty_data.json";
import validPingWithType from "../../../contracts/ws/v1/fixtures/envelope/valid_ping_with_type.json";
import validSnapshotEnvelope from "../../../contracts/ws/v1/fixtures/envelope/valid_snapshot_envelope.json";
import snapshotOk from "../../../contracts/ws/v1/fixtures/snapshot_ok.json";
import snapshotPartial from "../../../contracts/ws/v1/fixtures/snapshot_partial.json";
import snapshotUnavailable from "../../../contracts/ws/v1/fixtures/snapshot_unavailable.json";

import { parseServerMessage, PingDataSchema } from "../../src/infrastructure/ws/schemas";

const rootSnapshots = [
  { name: "snapshot_ok.json", payload: snapshotOk },
  { name: "snapshot_partial.json", payload: snapshotPartial },
  { name: "snapshot_unavailable.json", payload: snapshotUnavailable },
];

describe("snapshot envelope fixtures (shared with the backend)", () => {
  it("parses the real serializer envelope fixture", () => {
    expect(() => parseServerMessage(validSnapshotEnvelope)).not.toThrow();
  });

  it.each(rootSnapshots)("parses published $name", ({ payload }) => {
    expect(() => parseServerMessage(payload)).not.toThrow();
  });

  it("carries the snapshot discriminator on the wire, not a Zod default", () => {
    expect(validSnapshotEnvelope.data.type).toBe("snapshot");
    expect(validSnapshotEnvelope.data.meta.dropped_since_last).toBe(0);
  });

  it("rejects the envelope whose data.type is not snapshot", () => {
    expect(() => parseServerMessage(invalidSnapshotEnvelopeDiscriminator)).toThrow();
  });

  it("rejects the envelope with no data.type at all", () => {
    expect(() => parseServerMessage(invalidSnapshotEnvelopeMissingDiscriminator)).toThrow();
  });
});

describe("ping payloads", () => {
  /*
   * The published `pingData` schema declares `required: []` and
   * `properties: { type: { const: "ping" } }` with `additionalProperties: false`,
   * so both an empty `data` object and `{"type": "ping"}` are valid pings; snapshot-only
   * fields remain forbidden extras.
   */
  it("parses the published ping envelope with empty data", () => {
    expect(() => parseServerMessage(validPingEmptyData)).not.toThrow();
  });

  it("parses the published ping envelope with an explicit type", () => {
    expect(() => parseServerMessage(validPingWithType)).not.toThrow();
  });

  it("parses a minimal ping with either an explicit or defaulted type", () => {
    expect(() =>
      parseServerMessage({ v: 1, type: "ping", seq: 3, ts: 1000, data: { type: "ping" } }),
    ).not.toThrow();
    expect(() => parseServerMessage({ v: 1, type: "ping", seq: 3, ts: 1000, data: {} })).not.toThrow();
    expect(PingDataSchema.parse({})).toEqual({ type: "ping" });
    expect(PingDataSchema.parse({ type: "ping" })).toEqual({ type: "ping" });
  });

  it("rejects a ping carrying snapshot-only fields", () => {
    expect(() => parseServerMessage(invalidPingWithSnapshotFields)).toThrow();
  });
});
