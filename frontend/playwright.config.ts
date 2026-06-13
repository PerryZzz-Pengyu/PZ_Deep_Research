import { defineConfig, devices } from "@playwright/test";

const useSystemChrome = process.env.PLAYWRIGHT_USE_SYSTEM_CHROME === "1";
const reuseExistingServers = process.env.PLAYWRIGHT_REUSE_SERVERS === "1";
const backendPort = process.env.PLAYWRIGHT_BACKEND_PORT || "8000";
const frontendPort = process.env.PLAYWRIGHT_FRONTEND_PORT || "3000";
const backendUrl = `http://127.0.0.1:${backendPort}`;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: frontendUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(useSystemChrome ? { channel: "chrome" } : {}),
      },
    },
  ],
  webServer: [
    {
      command:
        `cd ../backend && MODEL_ROUTING_MODE=manual DEFAULT_PROVIDER=mock SEARCH_PROVIDER=mock MOCK_PROVIDER_DELAY_SECONDS=1.2 DATABASE_URL=sqlite+aiosqlite:////private/tmp/pz-deep-research-e2e-alembic.db DATABASE_MIGRATION_URL=sqlite+aiosqlite:////private/tmp/pz-deep-research-e2e-alembic.db PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${backendPort}`,
      url: `${backendUrl}/health`,
      reuseExistingServer: reuseExistingServers,
      timeout: 120_000,
    },
    {
      command: `NEXT_PUBLIC_API_BASE_URL=${backendUrl} npm run dev -- --hostname 127.0.0.1 --port ${frontendPort}`,
      url: frontendUrl,
      reuseExistingServer: reuseExistingServers,
      timeout: 120_000,
    },
  ],
});
