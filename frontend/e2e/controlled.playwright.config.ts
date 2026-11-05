import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

const FRONTEND_ORIGIN = "http://127.0.0.1:13001";

export default defineConfig({
  testDir: ".",
  testMatch: /recovery\.spec\.ts/,
  timeout: 60_000,
  use: { baseURL: FRONTEND_ORIGIN, headless: true },
  webServer: [
    {
      command:
        "VITE_E2E=true VITE_E2E_API=127.0.0.1:13001 npm run build -- --outDir dist-e2e-controlled --emptyOutDir && python3 -m http.server 13001 --bind 127.0.0.1 --directory ./dist-e2e-controlled",
      cwd: fileURLToPath(new URL("..", import.meta.url)),
      url: FRONTEND_ORIGIN,
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
