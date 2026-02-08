/**
 * save.spec.js — Dirty tracking, Cmd+S, unsaved changes guard.
 */

import { test, expect } from "@playwright/test";
import { setupPage, navToEditor, BASE } from "./fixtures.js";

test.beforeEach(async ({ page }) => {
  await setupPage(page);
});

test("dirty indicator absent on fresh editor load", async ({ page }) => {
  await navToEditor(page);
  await expect(page.locator(".dirty-indicator")).not.toBeVisible();
});

test("typing shows dirty indicator 'Unsaved changes'", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("new text");

  await expect(page.locator(".dirty-indicator")).toBeVisible();
  await expect(page.locator(".dirty-indicator")).toHaveText("Unsaved changes");
});

test("Meta+S dispatches batch save and clears dirty indicator", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("saved text");

  await expect(page.locator(".dirty-indicator")).toBeVisible();

  // Track that a PUT to /api/blocks/batch is called
  let batchSaved = false;
  await page.route(`${BASE}/api/blocks/batch`, async (route) => {
    batchSaved = true;
    await route.fulfill({ json: { success: true } });
  });

  await page.keyboard.press("Meta+s");

  // Wait for dirty indicator to clear
  await expect(page.locator(".dirty-indicator")).not.toBeVisible({ timeout: 3000 });
  expect(batchSaved).toBe(true);
});

test("navigate away while dirty → confirm dialog fires", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("unsaved");

  await expect(page.locator(".dirty-indicator")).toBeVisible();

  // Listen for dialog and accept it
  let dialogFired = false;
  page.on("dialog", async (dialog) => {
    dialogFired = true;
    expect(dialog.type()).toBe("confirm");
    expect(dialog.message()).toContain("unsaved");
    await dialog.accept();
  });

  // Click "Work" breadcrumb to navigate away
  await page.locator("#breadcrumb .breadcrumb-clickable").first().click();

  // Wait for navigation to complete
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });
  expect(dialogFired).toBe(true);
});

test("tab switch while dirty → confirm dialog fires", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("unsaved tab switch");

  await expect(page.locator(".dirty-indicator")).toBeVisible();

  let dialogFired = false;
  page.on("dialog", async (dialog) => {
    dialogFired = true;
    expect(dialog.type()).toBe("confirm");
    await dialog.accept();
  });

  // Switch tabs
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });
  expect(dialogFired).toBe(true);
});

test("window close while dirty → beforeunload fires", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("unsaved close");

  await expect(page.locator(".dirty-indicator")).toBeVisible();

  // Check that beforeunload handler calls preventDefault
  const prevented = await page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
  expect(prevented).toBe(true);
});

test("window close while clean → no beforeunload warning", async ({ page }) => {
  await navToEditor(page);

  // No edits — should not prevent close
  const prevented = await page.evaluate(() => {
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    return event.defaultPrevented;
  });
  expect(prevented).toBe(false);
});

test("sidebar block previews update after save", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();

  // Type distinctive text
  await page.keyboard.press("End");
  await page.keyboard.type(" UNIQUE_SAVE_MARKER");

  await expect(page.locator(".dirty-indicator")).toBeVisible();

  // Save
  await page.keyboard.press("Meta+s");
  await expect(page.locator(".dirty-indicator")).not.toBeVisible({ timeout: 3000 });

  // Sidebar should reflect updated content
  const sidebarText = await page.locator("#sidebar-list").textContent();
  expect(sidebarText).toContain("UNIQUE_SAVE_MARKER");
});
