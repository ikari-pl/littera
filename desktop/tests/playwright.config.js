import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.js",
  timeout: 15000,
  retries: 0,
  workers: 1, // serial — tests share a single browser context pattern
  use: {
    browserName: "chromium",
    headless: true,
    viewport: { width: 1280, height: 800 },
  },
  webServer: {
    command: "node tests/serve.js",
    cwd: "..",
    port: 5199,
    reuseExistingServer: true,
  },
});
