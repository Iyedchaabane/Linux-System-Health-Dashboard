import { z } from "zod";

/** Shared unavailable kinds mirrored from backend. */
export const UnavailableKindSchema = z.enum([
  "unsupported",
  "permission",
  "transient",
  "disabled",
]);

/** Group state (single metric). */
export const GroupStateOkSchema = z.object({
  status: z.literal("ok"),
  value: z.record(z.string(), z.unknown()).nullable(),
  partial: z.boolean().default(false),
});

export const GroupStateUnavailableSchema = z.object({
  status: z.literal("unavailable"),
  kind: UnavailableKindSchema,
  reason: z.string().min(1).max(512),
});

export const GroupStateSchema = z.discriminatedUnion("status", [
  GroupStateOkSchema,
  GroupStateUnavailableSchema,
]);

/** One process row; `cpu_percent` stays null until it has been measured. */
export const ProcessRowSchema = z.strictObject({
  pid: z.number().int().min(1),
  name: z.string().refine((value) => Array.from(value).length <= 128, {
    message: "Process name must contain at most 128 Unicode code points",
  }),
  cpu_percent: z.number().finite().min(0).nullable(),
  memory_rss_bytes: z.number().int().min(0),
});

/** Bounded process list carried by the optional `processes` group. */
export const ProcessesValueSchema = z.strictObject({
  items: z.array(ProcessRowSchema),
  skipped: z.number().int().min(0),
});

export const ProcessesGroupStateOkSchema = z.strictObject({
  status: z.literal("ok"),
  partial: z.boolean(),
  value: ProcessesValueSchema,
});

export const ProcessesGroupStateSchema = z.discriminatedUnion("status", [
  ProcessesGroupStateOkSchema,
  z.strictObject({
    status: z.literal("unavailable"),
    kind: UnavailableKindSchema,
    reason: z.string().min(1).max(512),
  }),
]);

/** Hello limits. */
export const HelloLimitsSchema = z.object({
  max_clients: z.number().int().min(1),
  max_clients_per_ip: z.number().int().min(1),
  max_message_bytes: z.number().int().min(1),
  rate_limit_burst: z.number().int().min(1),
  rate_limit_refill_per_second: z.number().min(0).max(100),
  send_timeout_seconds: z.number().min(0.5).max(30),
  handshake_timeout_seconds: z.number().min(0.5).max(30),
});

/** hello message data. */
export const HelloDataSchema = z.object({
  type: z.literal("hello").default("hello"),
  interval_ms: z.number().int().min(100).max(10000),
  max_message_bytes: z.number().int().min(1),
  groups: z.array(z.string()),
  server_time: z.number().min(0),
  limits: HelloLimitsSchema,
});

/** Bye message data. */
export const ByeDataSchema = z.object({
  type: z.literal("bye").default("bye"),
  reason: z.string().min(1).max(123),
});

/** Error message data. */
export const ErrorDataSchema = z.object({
  type: z.literal("error").default("error"),
  code: z.string().min(1).max(64),
  message: z.string().min(1).max(512),
});

/** ping/pong payloads are the literal name. */
export const PingDataSchema = z.strictObject({
  type: z.literal("ping").default("ping"),
});

export const PongDataSchema = z.object({
  type: z.literal("pong").default("pong"),
});

/** Snapshot metadata. */
export const SnapshotMetaSchema = z.object({
  dropped_since_last: z.number().int().min(0).optional(),
});

/**
 * Groups are a free-form record on the wire; `processes` is optional but, when
 * present, is validated against its strict typed shape.
 */
export const SnapshotGroupsSchema = z
  .record(z.string(), GroupStateSchema)
  .and(z.object({ processes: ProcessesGroupStateSchema.optional() }));

/** Snapshot payload. */
export const SnapshotDataSchema = z.object({
  type: z.literal("snapshot"),
  groups: SnapshotGroupsSchema,
  meta: SnapshotMetaSchema.nullable().optional(),
});

/** Outgoing client messages (subscribe/pong/ping). */
export const ClientSubscribeDataSchema = z.object({
  type: z.literal("subscribe").default("subscribe"),
  groups: z.array(z.string()).min(1),
});

/** The top-level envelope for server -> client. */
export const ServerMessageSchema = z.object({
  v: z.literal(1),
  type: z.enum(["hello", "snapshot", "error", "ping", "pong", "bye"]),
  seq: z.number().int().min(0),
  ts: z.number().int().min(0),
  data: z.unknown(),
});

/** Envelope dispatch: parse based on type. */
export function parseServerMessage(raw: unknown): ServerMessage {
  const message = ServerMessageSchema.parse(raw);
  switch (message.type) {
    case "hello":
      HelloDataSchema.parse(message.data);
      break;
    case "error":
      ErrorDataSchema.parse(message.data);
      break;
    case "bye":
      ByeDataSchema.parse(message.data);
      break;
    case "ping":
      PingDataSchema.parse(message.data);
      break;
    case "pong":
      PongDataSchema.parse(message.data);
      break;
    case "snapshot":
      SnapshotDataSchema.parse(message.data);
      break;
    default:
      throw new Error(`Unknown message type: ${String(message.type)}`);
  }
  return message as ServerMessage;
}

/** The top-level envelope for client -> server. */
export const ClientMessageSchema = z.object({
  v: z.literal(1),
  type: z.enum(["subscribe", "pong", "ping"]),
  seq: z.number().int().min(0),
  ts: z.number().int().min(0),
  data: z.unknown(),
});

export type ClientMessage = z.infer<typeof ClientMessageSchema>;

export function parseClientMessage(raw: unknown): ClientMessage {
  const message = ClientMessageSchema.parse(raw);
  switch (message.type) {
    case "subscribe":
      ClientSubscribeDataSchema.parse(message.data);
      break;
    case "pong":
      PongDataSchema.parse(message.data);
      break;
    case "ping":
      PingDataSchema.parse(message.data);
      break;
  }
  return message;
}

export type ServerMessage = z.infer<typeof ServerMessageSchema>;

/** Validation error shape matches our expected contract surface. */
export { z } from "zod";
