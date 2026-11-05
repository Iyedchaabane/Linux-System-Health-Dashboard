import { test, expect, type Page, type WebSocketRoute } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";

const hello = JSON.parse(readFileSync(new URL("../../contracts/ws/v1/fixtures/hello.json", import.meta.url), "utf8")) as typeof import("../../contracts/ws/v1/fixtures/hello.json");
const fixture = JSON.parse(readFileSync(new URL("../../contracts/ws/v1/fixtures/snapshot_ok.json", import.meta.url), "utf8")) as typeof import("../../contracts/ws/v1/fixtures/snapshot_ok.json");

function snapshot(seq: number, name: string, unavailable = false) {
  const frame = structuredClone(fixture);
  return { ...frame, seq, data: { ...frame.data, groups: {
    ...frame.data.groups,
    processes: unavailable
      ? { status: "unavailable", kind: "permission", reason: "Process listing is no longer permitted" }
      : { status: "ok", partial: false, value: {
        items: [{ pid: 1001, name, cpu_percent: 1, memory_rss_bytes: 1024 }], skipped: 0,
      } },
  } } };
}
const frames = {
  a: snapshot(100, "epoch-A"), b: snapshot(1, "epoch-B"), late: snapshot(101, "obsolete-A"),
  available: snapshot(100, "old-rest-row"), unavailable: snapshot(1, "", true),
  ten: snapshot(10, "seq-10"), nine: snapshot(9, "seq-9-stale"),
  duplicate: snapshot(10, "seq-10-duplicate"), eleven: snapshot(11, "seq-11"),
};
const rest = { ts: frames.available.ts, groups: frames.available.data.groups, meta: frames.available.data.meta };

// Validate exact generated frames (including the REST source and late callback)
// before navigation, using the existing Python validator, not another JS dependency.
test.beforeAll(() => {
  execFileSync(fileURLToPath(new URL("../../backend/.venv/bin/python", import.meta.url)), ["-B", "-c", `
import json, sys
from jsonschema import Draft202012Validator
from pathlib import Path
schema = json.loads(Path(sys.argv[1]).read_text())
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
for frame in json.load(sys.stdin):
    validator.validate(frame)
`, fileURLToPath(new URL("../../contracts/ws/v1/schemas/server_message.schema.json", import.meta.url))], {
    input: JSON.stringify([hello, ...Object.values(frames)]),
  });
});

type Probe = {
  messages: number; closes: number; consumed: number; status: number; error: string;
  inject: (data: string) => void;
};
declare global { interface Window { recoveryProbe: Probe } }

// HTML script executes after Playwright initialization but before the app module.
// Delegate native WebSocket API transport; retain only the actual A callback.
function installProbe() {
  Math.random = () => 0.5; // Deterministic full-jitter reconnect, test page only.
  const NativeSocket = window.WebSocket;
  const probe: Probe = window.recoveryProbe = {
    messages: 0, closes: 0, consumed: 0, status: 0, error: "",
    inject: () => { throw new Error("No captured callback"); },
  };
  let captured = false;
  window.WebSocket = class extends NativeSocket {
    constructor(url: string | URL, protocols?: string | string[]) {
      super(url, protocols);
      Object.defineProperty(this, "onmessage", { set: (callback: (event: MessageEvent) => void) => {
        if (!captured) {
          captured = true;
          probe.inject = (data) => {
            callback.call(this, new MessageEvent("message", { data }));
            probe.messages++;
          };
        }
        this.addEventListener("message", (event) => {
          callback.call(this, event);
          probe.messages++;
        });
      } });
      Object.defineProperty(this, "onclose", { set: (callback: (event: CloseEvent) => void) => {
        this.addEventListener("close", (event) => {
          callback.call(this, event);
          probe.closes++;
        });
      } });
    }
  };
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await nativeFetch(...args);
    if (response.url.endsWith("/api/v1/snapshot")) {
      probe.status = response.status;
      const json = response.json.bind(response);
      response.json = async () => {
        try {
          const value: unknown = await json();
          // Task barrier: the application's awaiting recovery continuation runs first.
          const channel = new MessageChannel();
          channel.port1.onmessage = () => {
            probe.consumed++;
            channel.port1.close(); channel.port2.close();
          };
          channel.port2.postMessage(null);
          return value;
        } catch (error) { probe.error = String(error); throw error; }
      };
    }
    return response;
  };
}

async function setup(page: Page) {
  const sockets: WebSocketRoute[] = [];
  await page.clock.install();
  await page.clock.pauseAt(new Date());
  await page.routeWebSocket("**/ws/v1/metrics", (socket) => { sockets.push(socket); });
  await page.route("**/", async (route) => {
    const response = await route.fetch();
    const html = (await response.text()).replace("<head>", `<head><script>(${installProbe.toString()})()</script>`);
    await route.fulfill({ response, body: html });
  });
  await page.goto("/");
  await expect.poll(() => sockets.length).toBe(1);
  return sockets;
}

async function rendered(page: Page) {
  await page.clock.runFor(32); // Two rendering opportunities, not a wall-clock sleep.
}
async function send(page: Page, socket: WebSocketRoute, frame: unknown) {
  const before = await page.evaluate(() => window.recoveryProbe.messages);
  socket.send(JSON.stringify(frame));
  await expect.poll(() => page.evaluate(() => window.recoveryProbe.messages)).toBe(before + 1);
  await rendered(page);
}
async function reconnect(page: Page, sockets: WebSocketRoute[]) {
  await sockets[0].close({ code: 1001, reason: "test restart" });
  await expect.poll(() => page.evaluate(() => window.recoveryProbe.closes)).toBe(1);
  await rendered(page);
  await expect(page.getByRole("region", { name: "Running processes", exact: true })).toContainText("Disconnected");
  await page.clock.runFor(1000); // First full-jitter reconnect is bounded by 1s.
  await expect.poll(() => sockets.length).toBe(2);
  await send(page, sockets[1], hello);
}
const row = (page: Page, name: string) => page.getByRole("rowheader", { name, exact: true });

test("A: new epoch accepts seq1 and ignores captured obsolete A callback", async ({ page }) => {
  await page.route("**/api/v1/snapshot", (route) => route.fulfill({ status: 503, json: {} }));
  const sockets = await setup(page);
  await send(page, sockets[0], hello);
  await send(page, sockets[0], frames.a);
  await expect(row(page, "epoch-A")).toBeVisible();
  await reconnect(page, sockets);
  await send(page, sockets[1], frames.b);
  await expect(row(page, "epoch-B")).toBeVisible();
  await expect(row(page, "epoch-A")).toHaveCount(0);
  const before = await page.evaluate(() => window.recoveryProbe.messages);
  await page.evaluate((data) => window.recoveryProbe.inject(data), JSON.stringify(frames.late));
  expect(await page.evaluate(() => window.recoveryProbe.messages)).toBe(before + 1);
  await rendered(page);
  await expect(row(page, "epoch-B")).toBeVisible();
  await expect(row(page, "obsolete-A")).toHaveCount(0);
});

test("B: consumed delayed REST cannot overwrite newer unavailable processes", async ({ page }) => {
  let release!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  let requested = 0;
  await page.route("**/api/v1/snapshot", async (route) => {
    requested++;
    await held;
    await route.fulfill({ status: 200, json: rest, headers: {
      "Access-Control-Allow-Origin": new URL(page.url()).origin,
    } });
  });
  try {
    const sockets = await setup(page);
    await send(page, sockets[0], hello);
    await send(page, sockets[0], frames.available);
    await expect(row(page, "old-rest-row")).toBeVisible();
    await reconnect(page, sockets);
    await expect.poll(() => requested).toBe(1);
    expect(await page.evaluate(() => window.recoveryProbe.consumed)).toBe(0);
    await send(page, sockets[1], frames.unavailable);
    const region = page.getByRole("region", { name: "Running processes", exact: true });
    await expect(region).toContainText("Process listing is no longer permitted");
    await expect(region.getByRole("table")).toHaveCount(0);
    release();
    await expect.poll(() => page.evaluate(() => window.recoveryProbe.consumed)).toBe(1);
    expect(await page.evaluate(() => ({ status: window.recoveryProbe.status, error: window.recoveryProbe.error })))
      .toEqual({ status: 200, error: "" });
    await rendered(page);
    await expect(region).toContainText("Process listing is no longer permitted");
    await expect(region.getByRole("table")).toHaveCount(0);
    await expect(row(page, "old-rest-row")).toHaveCount(0);
  } finally { release(); }
});

test("C: each out-of-order and duplicate frame is rejected before seq11", async ({ page }) => {
  const sockets = await setup(page);
  await send(page, sockets[0], hello);
  await send(page, sockets[0], frames.ten);
  await expect(row(page, "seq-10")).toBeVisible();
  for (const [frame, rejected] of [[frames.nine, "seq-9-stale"], [frames.duplicate, "seq-10-duplicate"]] as const) {
    await send(page, sockets[0], frame);
    await expect(row(page, "seq-10")).toBeVisible();
    await expect(row(page, rejected)).toHaveCount(0);
  }
  await send(page, sockets[0], frames.eleven);
  await expect(row(page, "seq-11")).toBeVisible();
  for (const name of ["seq-10", "seq-9-stale", "seq-10-duplicate"]) {
    await expect(row(page, name)).toHaveCount(0);
  }
});
