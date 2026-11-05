/**
 * Playwright global setup: prove that the servers we talk to are the ones we
 * started, not some unrelated process that happens to hold the port.
 *
 * An HTTP 200 is not evidence of identity — a foreign service can answer 200,
 * 403 or anything else on the port. These checks fail unless:
 *   1. `:18080/api/v1/healthz` returns exactly the app's health payload.
 *   2. `:18080/api/v1/snapshot` reports the deterministic fake CPU value
 *      (`cpu_total === 42.0`); a real host would report a different number and
 *      Jenkins would not report a snapshot at all.
 *   3. `:3000/` serves the built SPA (title marker present).
 *
 * Dependency-free: Node 20+ provides the global `fetch`.
 */

const BACKEND_ORIGIN = "http://127.0.0.1:18080";
const FRONTEND_ORIGIN = "http://127.0.0.1:3000";

const POLL_INTERVAL_MS = 250;
const READINESS_TIMEOUT_MS = 20_000;

const EXPECTED_HEALTH = { status: "ok" };
const EXPECTED_FAKE_CPU_TOTAL = 42.0;
const SPA_TITLE = "Linux System Health Dashboard";

type PollResult<T> = { ok: true; value: T } | { ok: false; detail: string };

async function poll<T>(
  label: string,
  attempt: () => Promise<PollResult<T>>,
): Promise<T> {
  const deadline = Date.now() + READINESS_TIMEOUT_MS;
  let lastDetail = "no attempt completed";

  while (Date.now() < deadline) {
    try {
      const result = await attempt();
      if (result.ok) {
        return result.value;
      }
      lastDetail = result.detail;
    } catch (error) {
      lastDetail = `request failed: ${error instanceof Error ? error.message : String(error)}`;
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  throw new Error(
    `E2E readiness check "${label}" failed after ${READINESS_TIMEOUT_MS} ms. ` +
      `Last observation: ${lastDetail}. ` +
      `Is the process on this port really the E2E fake app (tests.e2e.app_with_fakes) ` +
      `and not an unrelated service?`,
  );
}

async function expectHealth(): Promise<{ status: string }> {
  const url = `${BACKEND_ORIGIN}/api/v1/healthz`;
  return poll(`GET ${url}`, async () => {
    const response = await fetch(url);
    if (!response.ok) {
      return { ok: false, detail: `${url} returned HTTP ${response.status}` };
    }
    const body: unknown = await response.json();
    const observed = JSON.stringify(body);
    if (observed !== JSON.stringify(EXPECTED_HEALTH)) {
      return {
        ok: false,
        detail: `${url} body was ${observed}, expected ${JSON.stringify(EXPECTED_HEALTH)}`,
      };
    }
    // eslint-disable-next-line no-console
    console.log(`[e2e] backend healthz ${url} -> ${observed}`);
    return { ok: true, value: body as { status: string } };
  });
}

async function expectFakeSnapshot(): Promise<number> {
  const url = `${BACKEND_ORIGIN}/api/v1/snapshot`;
  return poll(`GET ${url} (fake cpu_total)`, async () => {
    const response = await fetch(url);
    if (!response.ok) {
      return { ok: false, detail: `${url} returned HTTP ${response.status}` };
    }
    const body = (await response.json()) as {
      groups?: { cpu?: { status?: string; value?: { cpu_total?: unknown } } };
    };
    const cpuTotal = body.groups?.cpu?.value?.cpu_total;
    if (typeof cpuTotal !== "number") {
      return {
        ok: false,
        detail: `${url} had no numeric groups.cpu.value.cpu_total (received ${JSON.stringify(body).slice(0, 300)})`,
      };
    }
    if (cpuTotal !== EXPECTED_FAKE_CPU_TOTAL) {
      return {
        ok: false,
        detail: `${url} reported cpu_total=${cpuTotal}, expected the fake reader value ${EXPECTED_FAKE_CPU_TOTAL} (this looks like a real host, not tests.e2e.app_with_fakes)`,
      };
    }
    // eslint-disable-next-line no-console
    console.log(`[e2e] backend snapshot ${url} -> groups.cpu.value.cpu_total=${cpuTotal}`);
    return { ok: true, value: cpuTotal };
  });
}

async function expectSpa(): Promise<string> {
  const url = `${FRONTEND_ORIGIN}/`;
  return poll(`GET ${url}`, async () => {
    const response = await fetch(url);
    if (!response.ok) {
      return { ok: false, detail: `${url} returned HTTP ${response.status}` };
    }
    const html = await response.text();
    if (!html.includes(SPA_TITLE)) {
      return {
        ok: false,
        detail: `${url} did not contain the SPA title "${SPA_TITLE}" (first 200 chars: ${html.slice(0, 200)})`,
      };
    }
    // eslint-disable-next-line no-console
    console.log(`[e2e] frontend ${url} -> contains title "${SPA_TITLE}"`);
    return { ok: true, value: SPA_TITLE };
  });
}

export default async function globalSetup(): Promise<void> {
  await expectHealth();
  await expectFakeSnapshot();
  await expectSpa();
}
