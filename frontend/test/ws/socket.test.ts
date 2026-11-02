import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { MetricsSocket } from "../../src/infrastructure/ws/MetricsSocket";

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

describe("MetricsSocket", () => {
  const states: string[] = [];

  beforeEach(() => {
    FakeWebSocket.onOpenCallback = null;
    FakeWebSocket.onMessageCallbacks = new Set();
    vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("connects and transitions to open", async () => {
    const s = new MetricsSocket({ url: "ws://localhost:8080/ws/v1/metrics", intervalMs: 200, onStateChange: (st) => states.push(st) });
    s.connect();
    await new Promise((r) => setTimeout(r, 10));
    expect(states).toContain("open");
    s.dispose();
  });

  it("counts invalid messages", async () => {
    const s = new MetricsSocket({ url: "ws://localhost:8080/ws/v1/metrics", intervalMs: 200 });
    s.connect();
    await new Promise((r) => setTimeout(r, 10));
    const handler = FakeWebSocket.onMessageCallbacks.values().next().value;
    const ev = new MessageEvent("message", { data: "not json" });
    if (handler) handler(ev);
    expect(s.getInvalidCount()).toBeGreaterThan(0);
    s.dispose();
  });

  it("does not invoke recover on first successful connect", async () => {
    const recover = vi.fn().mockResolvedValue(undefined);
    const s = new MetricsSocket({ url: "ws://localhost:8080/ws/v1/metrics", intervalMs: 200, recover });
    s.connect();
    await new Promise((r) => setTimeout(r, 20));
    expect(recover).not.toHaveBeenCalled();
    s.dispose();
  });

  it("dispose does not throw", () => {
    const s = new MetricsSocket({ url: "ws://localhost:8080/ws/v1/metrics" });
    s.connect();
    expect(() => s.dispose()).not.toThrow();
  });
});
