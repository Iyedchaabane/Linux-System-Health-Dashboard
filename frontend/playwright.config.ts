import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:3000", headless: true },
  webServer: [
    {
      command: "uv run uvicorn tests.e2e.app_with_fakes:app_factory --factory --host 127.0.0.1 --port 8080",
      url: "http://127.0.0.1:8080/api/v1/snapshot",
      cwd: "../backend",
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: "python3 -m http.server 3000 --directory ./dist",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: true,
      timeout: 15_000,
    },
  ],
});
