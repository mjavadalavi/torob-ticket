import { defineConfig } from "@playwright/test";

const externalBaseUrl = process.env.E2E_BASE_URL;
const baseURL = externalBaseUrl ?? "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    baseURL,
    locale: "fa-IR",
    timezoneId: "Asia/Tehran",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: externalBaseUrl
    ? undefined
    : [
        {
          command: "../backend/.venv/bin/uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8100",
          url: "http://127.0.0.1:8100/health",
          timeout: 30_000,
          reuseExistingServer: true,
        },
        {
          command: "API_URL=http://127.0.0.1:8100/api/v1 npm run dev -- --hostname 127.0.0.1 --port 3100",
          url: baseURL,
          timeout: 60_000,
          reuseExistingServer: true,
        },
      ],
});
