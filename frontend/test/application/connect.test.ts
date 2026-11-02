import { vi } from "vitest";
import { beforeEach, describe, expect, it } from "vitest";

import { useDashboardStore } from "../../src/application/store";
import { connectDashboard } from "../../src/application/connect";

class FakeWebSocket {
  static onOpenCallback: ((ev?: Event) => void) | null = null;
  static onMessageCallbacks = new Set<(ev: MessageEvent) => void>();
  readyState = 0;
  binaryType = "blob";
  url: string;
  subprotocol: string;
  constructor(url: string, protocols?: string) {
    this.url = url;
    this.subprotocol = protocols ?? "";
    setTimeout(() => {
      if (FakeWebSocket.onOpenCallback) FakeWebSocket.onOpenCallback();
    }, 0);
  }
  close = vi.fn();
  send = vi.fn();
  get onopen() { return FakeWebSocket.onOpenCallback; }
  set onopen(fn: ((ev?: Event) => void) | null) { FakeWebSocket.onOpenCallback = fn; }
  get onmessage() { return null; }
  set onmessage(fn: ((ev: MessageEvent) => void) | null) {
    if (fn) FakeWebSocket.onMessageCallbacks.add(fn);
  }
  get onclose() { return null; }
  set onclose(_fn: ((ev: CloseEvent) => void) | null) { /* noop */ }
  get onerror() { return null; }
  set onerror(_fn) { /* noop */ }
}

describe("connectDashboard", () => {
  beforeEach(() => {
    FakeWebSocket.onOpenCallback = null;
    FakeWebSocket.onMessageCallbacks = new Set();
    vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
    useDashboardStore.getState().reset();
  });

  it("connects socket and tracks hello + snapshot", async () => {
    const conn = connectDashboard({
      socketUrl: "ws://localhost:8080/ws/v1/metrics",
      intervalMs: 200,
      fetchSnapshot: async () => ({ groups: {}, seq: 1, ts: 1 }),
    });
    await new Promise((r) => setTimeout(r, 10));
    const handler = FakeWebSocket.onMessageCallbacks.values().next().value;
    if (handler) {
      handler(
        new MessageEvent("message", {
          data: JSON.stringify({ v: 1, type: "hello", seq: 0, ts: 1, data: { type: "hello", interval_ms: 250, max_message_bytes: 1, groups: ["cpu", "memory"], server_time: 1, limits: { max_clients: 1, max_clients_per_ip: 1, max_message_bytes: 1, rate_limit_burst: 1, rate_limit_refill_per_second: 1, send_timeout_seconds: 1, handshake_timeout_seconds: 1 } } }),
        }),
      );
    }
    await new Promise((r) => setTimeout(r, 5));
    expect(useDashboardStore.getState().intervalMs).not.toBe(1000);
    if (handler) {
      handler(
        new MessageEvent("message", {
          data: JSON.stringify({ v: 1, type: "snapshot", seq: 2, ts: 2, data: { type: "snapshot", groups: {}, meta: null } }),
        }),
      );
    }
    expect(useDashboardStore.getState().latestSnapshot?.seq).toBe(2);
    conn.dispose();
    vi.unstubAllGlobals();
  });
});
