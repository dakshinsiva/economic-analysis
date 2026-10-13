import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", colorScheme: "dark" },
  webServer: process.env.E2E_BASE_URL ? undefined : {
    command: "npm run dev", url: "http://localhost:3000", reuseExistingServer: true, timeout: 120_000,
    env: { NEXT_PUBLIC_DEMO: "1" },
  },
});
