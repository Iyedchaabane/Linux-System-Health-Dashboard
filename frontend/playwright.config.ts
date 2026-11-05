import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

/**
 * E2E environment.
 *
 * Ports are dedicated to E2E and never reused from a foreign process:
 * `reuseExistingServer: false` makes Playwright fail loudly when something else
 * already listens on 3000 or 18080 (for example the unrelated service that owns
 * 8080 on developer machines). Readiness for the backend is checked against
 * `/api/v1/healthz` — an endpoint only the fake test app answers — and
 * `e2e/global-setup.ts` additionally proves the process identity by checking
 * the deterministic fake metric values.
 */
const BACKEND_ORIGIN = "http://127.0.0.1:18080";
const FRONTEND_ORIGIN = "http://127.0.0.1:3000";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: /recovery\.spec\.ts/,
  globalSetup: "./e2e/global-setup.ts",
  timeout: 30_000,
  use: { baseURL: FRONTEND_ORIGIN, headless: true },
  webServer: [
    {
      command:
        "uv run uvicorn tests.e2e.app_with_fakes:app_factory --factory --host 127.0.0.1 --port 18080",
      url: `${BACKEND_ORIGIN}/api/v1/healthz`,
      cwd: fileURLToPath(new URL("../backend", import.meta.url)),
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // Build a dedicated E2E bundle (the production `dist/` is left untouched)
      // with the E2E backend origin compiled in, then serve it statically.
      command:
        "VITE_E2E=true VITE_E2E_API=127.0.0.1:18080 npm run build -- --outDir dist-e2e --emptyOutDir && python3 -m http.server 3000 --bind 127.0.0.1 --directory ./dist-e2e",
      cwd: fileURLToPath(new URL(".", import.meta.url)),
      url: FRONTEND_ORIGIN,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
