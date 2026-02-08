/**
 * entities.spec.js — Entity tab, detail view, CRUD.
 */

import { test, expect } from "@playwright/test";
import { setupPage, gotoApp, navToDocument, navToSection, MOCK_DATA } from "./fixtures.js";

test.beforeEach(async ({ page }) => {
  await setupPage(page);
});

test("click Entities tab → sidebar shows entities with type badges", async ({ page }) => {
  await gotoApp(page);
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  const items = page.locator("#sidebar-list .sidebar-item");
  await expect(items).toHaveCount(3);

  // First entity has badge + label
  const firstBadge = items.first().locator(".entity-badge");
  await expect(firstBadge).toHaveText("concept");
  await expect(items.first()).toContainText("Concept");
});

test("click entity → content shows detail header with badge + name", async ({ page }) => {
  await gotoApp(page);
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });
  await page.locator("#sidebar-list .sidebar-item").first().click();

  // Wait for entity detail to render
  await expect(page.locator(".entity-header")).toBeVisible();
  await expect(page.locator(".entity-header .entity-badge")).toHaveText("concept");
  await expect(page.locator(".entity-header h2")).toHaveText("Concept");
});

test("entity detail shows labels section", async ({ page }) => {
  await gotoApp(page);
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });
  await page.locator("#sidebar-list .sidebar-item").first().click();
  await page.locator(".entity-header").waitFor({ state: "visible" });

  // Labels section with language badges and base_form
  const labelRows = page.locator(".entity-label-row");
  await expect(labelRows).toHaveCount(2);
  await expect(labelRows.first().locator(".lang-badge")).toHaveText("en");
  await expect(labelRows.first()).toContainText("Concept");
  await expect(labelRows.nth(1).locator(".lang-badge")).toHaveText("pl");
  await expect(labelRows.nth(1)).toContainText("Pojęcie");
});

test("entity detail shows note section with content", async ({ page }) => {
  await gotoApp(page);
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });
  await page.locator("#sidebar-list .sidebar-item").first().click();
  await page.locator(".entity-header").waitFor({ state: "visible" });

  await expect(page.locator(".entity-note")).toHaveText("A fundamental idea.");
});

test("entity detail shows '(no note)' when note is empty", async ({ page }) => {
  await gotoApp(page);
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  // Click second entity (Ada Lovelace) which has empty note
  await page.locator("#sidebar-list .sidebar-item").nth(1).click();
  await page.locator(".entity-header").waitFor({ state: "visible" });

  await expect(page.locator(".entity-note")).toHaveText("(no note)");
  await expect(page.locator(".entity-note")).toHaveClass(/entity-note-empty/);
});

test("entity detail shows mentions section", async ({ page }) => {
  await gotoApp(page);
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });
  await page.locator("#sidebar-list .sidebar-item").first().click();
  await page.locator(".entity-header").waitFor({ state: "visible" });

  const mentionRow = page.locator(".mention-row");
  await expect(mentionRow).toHaveCount(1);
  await expect(mentionRow.locator(".mention-path")).toContainText("First Document");
  await expect(mentionRow.locator(".mention-path")).toContainText("Introduction");
  await expect(mentionRow.locator(".mention-preview")).toContainText("Concept mention");
});

test("tab active class toggles correctly", async ({ page }) => {
  await gotoApp(page);

  // Initially outline is active
  await expect(page.locator("#tab-outline")).toHaveClass(/tab-active/);
  await expect(page.locator("#tab-entities")).not.toHaveClass(/tab-active/);

  // Switch to entities
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  await expect(page.locator("#tab-entities")).toHaveClass(/tab-active/);
  await expect(page.locator("#tab-outline")).not.toHaveClass(/tab-active/);

  // Switch back
  await page.locator("#tab-outline").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  await expect(page.locator("#tab-outline")).toHaveClass(/tab-active/);
  await expect(page.locator("#tab-entities")).not.toHaveClass(/tab-active/);
});

test("breadcrumb click from entities view resets to outline view (Bug 1 regression)", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);

  // Switch to entities tab
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  // Click "Work" breadcrumb — should reset to outline view at root
  await page.locator("#breadcrumb .breadcrumb-clickable").first().click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  // Should be back in outline view showing documents
  await expect(page.locator("#tab-outline")).toHaveClass(/tab-active/);
  await expect(page.locator("#sidebar-list .sidebar-item").first()).toHaveText(/First Document/);
});

test("tab switch while editing closes editor (Bug 2 regression)", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);
  await navToSection(page);

  // Editor should be active
  await expect(page.locator("#prosemirror-editor")).toBeVisible();

  // Switch to entities — should close editor
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  // Editor should be gone
  await expect(page.locator("#prosemirror-editor")).not.toBeVisible();
});

test("add entity button present in entities view", async ({ page }) => {
  await gotoApp(page);
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  await expect(page.locator("#sidebar-actions .sidebar-action-btn")).toBeVisible();
});

test("delete entity button present on entity items", async ({ page }) => {
  await gotoApp(page);
  await page.locator("#tab-entities").click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  const delBtns = page.locator("#sidebar-list .sidebar-item .sidebar-delete-btn");
  await expect(delBtns).toHaveCount(3);
});
