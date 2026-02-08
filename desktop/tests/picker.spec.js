/**
 * picker.spec.js — Work directory picker screen tests.
 */

import { test, expect } from "@playwright/test";
import { setupPage, APP_URL, MOCK_DATA } from "./fixtures.js";

test.beforeEach(async ({ page }) => {
  await setupPage(page);
});

test("picker screen shows on launch", async ({ page }) => {
  await page.goto(APP_URL);
  const picker = page.locator("#picker");
  await expect(picker).toBeVisible({ timeout: 5000 });
  // No sidebar should exist yet
  await expect(page.locator("#sidebar")).toHaveCount(0);
});

test("picker shows 'Littera' heading and subtitle", async ({ page }) => {
  await page.goto(APP_URL);
  await page.locator("#picker").waitFor({ state: "visible", timeout: 5000 });
  await expect(page.locator(".picker-header h1")).toHaveText("Littera");
  await expect(page.locator(".picker-header p")).toHaveText("Select a work to open");
});

test("recent works are listed", async ({ page }) => {
  await page.goto(APP_URL);
  await page.locator("#picker").waitFor({ state: "visible", timeout: 5000 });
  const items = page.locator(".picker-work-item");
  // 2 recent + 1 workspace work = 3 total
  await expect(items).toHaveCount(3);
  // First recent work
  await expect(items.nth(0).locator(".picker-work-name")).toHaveText("my-work");
  await expect(items.nth(0).locator(".picker-work-path")).toHaveText("/home/user/my-work");
});

test("clicking recent work transitions to main UI", async ({ page }) => {
  await page.goto(APP_URL);
  await page.locator(".picker-work-item").first().waitFor({ state: "visible", timeout: 5000 });

  // Click the first recent work
  await page.locator(".picker-work-item").first().click();

  // Should transition to main UI with sidebar
  await page.locator("#sidebar").waitFor({ state: "visible", timeout: 5000 });
  await expect(page.locator("#picker")).toHaveCount(0);

  // Documents should be loaded
  const items = page.locator("#sidebar-list .sidebar-item");
  await expect(items).toHaveCount(2);
});

test("'Open Work' and 'New Work' buttons are present", async ({ page }) => {
  await page.goto(APP_URL);
  await page.locator("#picker").waitFor({ state: "visible", timeout: 5000 });

  const buttons = page.locator(".picker-btn");
  await expect(buttons).toHaveCount(2);
  await expect(buttons.nth(0)).toHaveText("Open Work\u2026");
  await expect(buttons.nth(1)).toHaveText("New Work\u2026");
});

test("workspace config section is visible", async ({ page }) => {
  await page.goto(APP_URL);
  await page.locator("#picker").waitFor({ state: "visible", timeout: 5000 });

  const wsConfig = page.locator(".picker-workspace-config");
  await expect(wsConfig).toBeVisible();
  // Should show workspace path and "Change Workspace" link
  await expect(wsConfig.locator(".picker-work-path")).toHaveText("/home/user/workspace");
  await expect(wsConfig.locator(".picker-btn-link")).toHaveText("Change Workspace");
});

test("workspace works section is shown", async ({ page }) => {
  await page.goto(APP_URL);
  await page.locator("#picker").waitFor({ state: "visible", timeout: 5000 });

  // The workspace section should list project-a
  const sections = page.locator(".picker-section");
  await expect(sections).toHaveCount(2); // "Recent Works" + "Workspace"

  const wsSection = sections.nth(1);
  await expect(wsSection.locator("h2")).toHaveText("Workspace");
  await expect(wsSection.locator(".picker-work-name")).toHaveText("project-a");
});
