import { defineConfig, devices } from "@playwright/test";

const useSystemChrome = process.env.PLAYWRIGHT_USE_SYSTEM_CHROME === "1";
const reuseExistingServers = process.env.PLAYWRIGHT_REUSE_SERVERS === "1";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:3000",
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
        "cd ../backend && DEFAULT_PROVIDER=mock SEARCH_PROVIDER=mock MOCK_PROVIDER_DELAY_SECONDS=1.2 DATABASE_URL=sqlite+aiosqlite:////private/tmp/pz-deep-research-e2e-alembic.db PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: reuseExistingServers,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: reuseExistingServers,
      timeout: 120_000,
    },
  ],
});
