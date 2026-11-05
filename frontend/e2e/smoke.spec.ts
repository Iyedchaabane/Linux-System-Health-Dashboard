import { test, expect } from "@playwright/test";

/**
 * Functional E2E coverage against the fake-composition backend on 127.0.0.1:18080
 * and a statically served production build on 127.0.0.1:3000.
 *
 * Values asserted here are the deterministic fake reader values from
 * `backend/tests/e2e/fakes.py`; the readiness identity check in
 * `e2e/global-setup.ts` guarantees we are not talking to a real host or a
 * foreign process.
 */
const E2E_BACKEND_PORT = "18080";
const LIVE_VALUE_TIMEOUT = 15_000;

test("dashboard loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Linux System Health Dashboard" })).toBeVisible();
});

test("dashboard displays core metric cards", async ({ page }) => {
  await page.goto("/");
  for (const name of ["CPU", "Memory", "Disk", "Network"]) {
    await expect(page.getByRole("article", { name: `${name} metric` })).toBeVisible();
  }
});

test("theme toggle switches themes", async ({ page }) => {
  await page.goto("/");
  const button = page.getByRole("button", { name: /Theme switch/i });
  await expect(button).toBeVisible();
  const before = (await button.textContent())?.trim() ?? "";
  await button.click();
  const after = (await button.textContent())?.trim() ?? "";
  expect(before).not.toBe(after);
});

test("real metric values from the live feed reach the browser", async ({ page }) => {
  await page.goto("/");

  // CPU: fake reader reports cpu_total = 42.0 -> "42.0%"
  await expect(page.getByRole("article", { name: "CPU metric" })).toContainText("42.0%", {
    timeout: LIVE_VALUE_TIMEOUT,
  });

  // Memory: fake reader reports used_percent = 64.0 -> "64.0%"
  await expect(page.getByRole("article", { name: "Memory metric" })).toContainText("64.0%", {
    timeout: LIVE_VALUE_TIMEOUT,
  });

  // Network: the wire carries cumulative counters, the card must show a derived
  // per-second rate. The fake counters are constant, so the honest rate is
  // 0 B/s — what matters is that a rate exists and no cumulative total is shown.
  const networkCard = page.getByRole("article", { name: "Network metric" });
  await expect(networkCard).toContainText("Download", { timeout: LIVE_VALUE_TIMEOUT });
  await expect(networkCard).toContainText("B/s", { timeout: LIVE_VALUE_TIMEOUT });
  await expect(networkCard).not.toContainText("--");
  await expect(networkCard).not.toContainText(/cumulative/i);
});

test("the live feed uses a real WebSocket exchange that carries a snapshot", async ({ page }) => {
  const sockets: { url: string; frames: string[] }[] = [];

  page.on("websocket", (ws) => {
    const record = { url: ws.url(), frames: [] as string[] };
    sockets.push(record);
    ws.on("framereceived", (frame) => {
      record.frames.push(frameText(frame.payload));
    });
  });

  await page.goto("/");
  // Wait until a value has actually been rendered, so a socket exchange must have happened.
  await expect(page.getByRole("article", { name: "CPU metric" })).toContainText("42.0%", {
    timeout: LIVE_VALUE_TIMEOUT,
  });

  const observed = sockets.map((socket) => socket.url).join(", ") || "<none>";
  const metricsSocket = sockets.find((socket) => socket.url.endsWith("/ws/v1/metrics"));
  expect(metricsSocket, `expected a /ws/v1/metrics socket; observed: ${observed}`).toBeDefined();

  const parsedUrl = new URL(metricsSocket!.url);
  expect(parsedUrl.pathname).toBe("/ws/v1/metrics");
  expect(parsedUrl.port, `socket URL was ${metricsSocket!.url}`).toBe(E2E_BACKEND_PORT);

  const parsedFrames = metricsSocket!.frames
    .map((frame) => {
      try {
        return JSON.parse(frame) as Record<string, unknown>;
      } catch {
        return null;
      }
    })
    .filter((message): message is Record<string, unknown> => message !== null);

  const snapshotMessages = parsedFrames.filter((message) => message["type"] === "snapshot");
  expect(
    snapshotMessages.length,
    `expected at least one parsed snapshot frame on ${metricsSocket!.url}; ` +
      `received ${metricsSocket!.frames.length} frame(s): ${metricsSocket!.frames
        .map((frame) => frame.slice(0, 120))
        .join(" | ")}`,
  ).toBeGreaterThan(0);

  // The streamed snapshot itself must carry the deterministic fake CPU value.
  const cpuValues = snapshotMessages.map((message) => {
    const data = message["data"] as { groups?: { cpu?: { value?: { cpu_total?: unknown } } } } | undefined;
    return data?.groups?.cpu?.value?.cpu_total;
  });
  expect(cpuValues, `snapshot cpu_total values: ${JSON.stringify(cpuValues)}`).toContain(42);

  // eslint-disable-next-line no-console
  console.log(
    `[e2e] websocket ${metricsSocket!.url} frames=${metricsSocket!.frames.length} ` +
      `snapshots=${snapshotMessages.length} cpu_total=${JSON.stringify(cpuValues.slice(0, 3))}`,
  );
});

const NAV_PAGES = [
  {
    path: "/",
    label: "Overview",
    headings: ["Storage", "Running processes", "Temperature"],
    cards: ["CPU", "Memory", "Disk", "Network", "Storage"],
  },
  { path: "/cpu", label: "CPU", headings: ["CPU usage"], cards: ["CPU"] },
  { path: "/memory", label: "Memory", headings: ["Memory used"], cards: ["Memory"] },
  {
    path: "/network",
    label: "Network",
    headings: ["Network receive", "Network transmit"],
    cards: ["Download", "Upload"],
  },
  { path: "/disks", label: "Disks", headings: ["Disk"], cards: ["Disk"] },
] as const;

test("desktop sidebar navigates between every page", async ({ page }) => {
  await page.goto("/");

  // Scope to the desktop sidebar: a second (mobile) nav repeats the same labels.
  const primaryNav = page.locator('nav[aria-label="Primary"]');
  await expect(primaryNav).toBeVisible();

  for (const target of NAV_PAGES) {
    const link = primaryNav.getByRole("link", { name: target.label, exact: true });
    await link.click();

    // Client-side routing: python3 -m http.server has no SPA history fallback,
    // so a real navigation to /cpu would 404. The path must change without it.
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 5_000 }).toBe(target.path);

    for (const heading of target.headings) {
      // `/disks` renders the word "Disk" twice (card title and chart title), so
      // assert presence rather than strict uniqueness.
      await expect(
        page.getByRole("heading", { name: heading, exact: true }).first(),
      ).toBeVisible();
    }
    for (const card of target.cards) {
      await expect(page.getByRole("article", { name: `${card} metric` })).toBeVisible();
    }

    // NavLink marks the active anchor with aria-current="page".
    await expect(link).toHaveAttribute("aria-current", "page");
    for (const other of NAV_PAGES) {
      if (other.path === target.path) continue;
      const otherLink = primaryNav.getByRole("link", { name: other.label, exact: true });
      await expect(otherLink).not.toHaveAttribute("aria-current", "page");
    }
  }
});

/** Playwright delivers text frames as strings and binary frames as Buffers. */
function frameText(payload: unknown): string {
  if (typeof payload === "string") return payload;
  if (payload && typeof payload === "object" && typeof (payload as { toString(): string }).toString === "function") {
    return (payload as { toString(encoding?: string): string }).toString("utf8");
  }
  return String(payload);
}
