import { parseServerMessage } from "./schemas";
import type { ServerMessage } from "./schemas";
import { calculateBackoff, isFatalCode } from "./backoff";

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "open"
  | "stale"
  | "closed"
  | "fatal";

export type MetricsSocketOptions = {
  url: string;
  intervalMs?: number;
  onMessage?: (msg: ServerMessage) => void;
  onStateChange?: (state: ConnectionStatus, reason?: string) => void;
  onInvalidMessage?: (count: number) => void;
  onReconnectAttempt?: () => void;
  recover?: () => void | Promise<void>;
};

const DEFAULT_INTERVAL_MS = 1000;
const INVALID_THRESHOLD = 5;

export class MetricsSocket {
  private ws: WebSocket | null = null;
  private options: MetricsSocketOptions;
  private retryCount = 0;
  private healthySince = 0;
  private needsRecovery = false;
  private recoveryInFlight = false;
  private staleTimer: ReturnType<typeof setTimeout> | null = null;
  private stopped = false;
  private intervalMs = DEFAULT_INTERVAL_MS;
  private invalidCount = 0;
  private state: ConnectionStatus = "idle";

  constructor(options: MetricsSocketOptions) {
    // Validate protocol subprotocol via constructing URL with subprotocol implicitly
    this.options = options;
    this.intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS;
  }

  connect(): void {
    this.stopped = false;
    this._open();
  }

  dispose(): void {
    this.stopped = true;
    this._cleanup();
  }

  getState(): ConnectionStatus {
    return this.state;
  }

  getInvalidCount(): number {
    return this.invalidCount;
  }

  private _setState(next: ConnectionStatus, reason?: string): void {
    this.state = next;
    this.options.onStateChange?.(next, reason);
  }

  private _cleanStaleTimer(): void {
    if (this.staleTimer !== null) {
      clearTimeout(this.staleTimer);
      this.staleTimer = null;
    }
  }

  private _cleanup(): void {
    this._cleanStaleTimer();
    if (this.ws) {
      try {
        this.ws.close(1000, "dispose");
      } catch {
        /* ignore */
      }
      this.ws = null;
    }
  }

  private _open(): void {
    if (this.stopped) return;
    this._setState("connecting");
    const url = this.options.url;
    // Native WebSocket accepts protocols as second argument
    const ws = new WebSocket(url, "monitor.v1");
    this.ws = ws;
    this.ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      this.healthySince = Date.now();
      this._setState("open");
      const shouldRecover = this.needsRecovery;
      this.needsRecovery = false;
      if (!shouldRecover) return;
      if (typeof this.options.recover !== "function") return;
      if (this.recoveryInFlight) return;
      this.recoveryInFlight = true;
      try {
        const result = this.options.recover();
        if (result && typeof (result as Promise<void>).then === "function") {
          (result as Promise<void>)
            .catch(() => undefined)
            .finally(() => {
              this.recoveryInFlight = false;
            });
        } else {
          this.recoveryInFlight = false;
        }
      } catch {
        this.recoveryInFlight = false;
      }
    };

    ws.onmessage = (event: MessageEvent) => {
      this._cleanStaleTimer();
      let raw: unknown = null;
      try {
        raw = JSON.parse(String(event.data));
      } catch {
        this._handleInvalid();
        return;
      }
      try {
        const msg = parseServerMessage(raw);
        this._handleMessage(msg);
      } catch {
        this._handleInvalid();
        return;
      }
      this._scheduleStale();
    };

    ws.onclose = (event: CloseEvent) => {
      this._cleanStaleTimer();
      if (event.code === 1000 || this.stopped) {
        this._setState("closed", `${event.code}`);
        return;
      }
      if (isFatalCode(event.code)) {
        this._setState("fatal", `${event.code}`);
        return;
      }
      this.needsRecovery = true;
      // reconnect
      this._setState("closed", `${event.code}`);
      const is1013 = event.code === 1013;
      const delayMs = calculateBackoff({
        baseMs: is1013 ? 10000 : 1000,
        capMs: 30000,
        retryCount: this.retryCount,
        jitter: "full",
      });
      // reset retry after 30s of health
      if (this.healthySince > 0 && Date.now() - this.healthySince > 30_000) {
        this.retryCount = 0;
      }
      this.retryCount += 1;
      this.options.onReconnectAttempt?.();
      setTimeout(() => this._open(), delayMs);
    };

    ws.onerror = () => {
      // onclose handles reconnect
    };
  }

  private _handleMessage(msg: ServerMessage): void {
    // Track seq gaps by comparing with previous seq
    // Hello/bye are not seq'd for gap concerns (hello seq 0)
    // Update interval from hello
    if (msg.type === "hello") {
      const data = msg.data as { interval_ms?: number };
      if (typeof data?.interval_ms === "number") {
        this.intervalMs = data.interval_ms;
      }
    }
    this.options.onMessage?.(msg);
  }

  private _handleInvalid(): void {
    this.invalidCount += 1;
    this.options.onInvalidMessage?.(this.invalidCount);
    if (this.invalidCount > INVALID_THRESHOLD) {
      // close + reconnect
      if (this.ws) {
        this.ws.close(4400, "invalid repeated messages");
      }
    }
  }

  private _scheduleStale(): void {
    this._cleanStaleTimer();
    const interval = this.intervalMs;
    const staleMs = interval * 2;
    const reconnectMs = interval * 4;
    // At staleMs -> mark stale
    const timer = setTimeout(() => {
      this._setState("stale");
      // At reconnectMs -> close and reconnect
      const timer2 = setTimeout(() => {
        if (this.ws) {
          this.ws.close(1000, "stale connection");
        }
      }, reconnectMs - staleMs);
      if (timer2 !== null) {
        this.staleTimer = timer2 as unknown as ReturnType<typeof setTimeout>;
      }
    }, staleMs);
    this.staleTimer = timer;
  }

  /** Manually trigger reconnection fetch of snapshot (caller supplies REST fn). */
  fetchSnapshot(_fetcher: () => Promise<unknown>): void {
    _fetcher().catch(() => undefined);
  }
}
