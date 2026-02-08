/**
 * mentions.spec.js — Mention popup, pill rendering, click-to-navigate.
 */

import { test, expect } from "@playwright/test";
import { setupPage, navToEditor, MOCK_DATA } from "./fixtures.js";

test.beforeEach(async ({ page }) => {
  await setupPage(page);
});

test("typing '@' triggers mention popup", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("@");

  await expect(page.locator(".mention-popup")).toBeVisible({ timeout: 3000 });
});

test("popup shows entity items with labels and type badges", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("@");

  const popup = page.locator(".mention-popup");
  await expect(popup).toBeVisible({ timeout: 3000 });

  const items = popup.locator(".mention-item");
  await expect(items).toHaveCount(3);

  // Check first item has label and type
  await expect(items.first().locator(".mention-item-label")).toHaveText("Concept");
  await expect(items.first().locator(".mention-item-type")).toHaveText("concept");
});

test("arrow keys navigate popup selection", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("@");

  const popup = page.locator(".mention-popup");
  await expect(popup).toBeVisible({ timeout: 3000 });

  // First item is selected by default
  await expect(popup.locator(".mention-item.selected")).toHaveCount(1);
  const firstLabel = await popup.locator(".mention-item.selected .mention-item-label").textContent();

  // Arrow down
  await page.keyboard.press("ArrowDown");
  const secondLabel = await popup.locator(".mention-item.selected .mention-item-label").textContent();
  expect(secondLabel).not.toBe(firstLabel);

  // Arrow up — back to first
  await page.keyboard.press("ArrowUp");
  const backLabel = await popup.locator(".mention-item.selected .mention-item-label").textContent();
  expect(backLabel).toBe(firstLabel);
});

test("Enter inserts mention pill", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("@");

  await page.locator(".mention-popup").waitFor({ state: "visible", timeout: 3000 });
  await page.keyboard.press("Enter");

  // Mention pill should appear
  const pill = pm.locator(".mention-pill");
  await expect(pill.first()).toBeVisible();
});

test("mention pill has correct data-entity-id attribute", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("@");

  await page.locator(".mention-popup").waitFor({ state: "visible", timeout: 3000 });
  // First entity is "Concept" with id "ent-1"
  await page.keyboard.press("Enter");

  const pill = pm.locator(".mention-pill").last();
  await expect(pill).toHaveAttribute("data-entity-id", "ent-1");
});

test("mention pill has cursor: pointer style", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");

  // The editor should have loaded blocks, and block 2 has a mention
  // Check any existing mention pill from loaded content
  const pill = pm.locator(".mention-pill").first();

  // If no existing mention, create one
  const count = await pill.count();
  if (count === 0) {
    await pm.click();
    await page.keyboard.press("End");
    await page.keyboard.type("@");
    await page.locator(".mention-popup").waitFor({ state: "visible", timeout: 3000 });
    await page.keyboard.press("Enter");
  }

  const cursor = await pm.locator(".mention-pill").first().evaluate((el) => {
    return window.getComputedStyle(el).cursor;
  });
  expect(cursor).toBe("pointer");
});

test("clicking mention pill navigates to entity detail (Bug 3 regression)", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");

  // Insert a mention pill for a known entity
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("@");
  await page.locator(".mention-popup").waitFor({ state: "visible", timeout: 3000 });
  await page.keyboard.press("Enter"); // inserts "Concept" (ent-1)

  // Click the mention pill
  const pill = pm.locator(".mention-pill").last();
  await pill.click();

  // Should navigate to entities view with detail showing
  await expect(page.locator("#tab-entities")).toHaveClass(/tab-active/);
  await expect(page.locator(".entity-header")).toBeVisible();
  await expect(page.locator(".entity-header h2")).toHaveText("Concept");
});

test("Escape dismisses mention popup", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("End");
  await page.keyboard.type("@");

  await page.locator(".mention-popup").waitFor({ state: "visible", timeout: 3000 });
  await page.keyboard.press("Escape");
  await expect(page.locator(".mention-popup")).not.toBeVisible();
});
