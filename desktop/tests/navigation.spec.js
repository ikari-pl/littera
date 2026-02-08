/**
 * navigation.spec.js — Outline nav, breadcrumbs, tab switching.
 */

import { test, expect } from "@playwright/test";
import { setupPage, gotoApp, navToDocument, navToSection, MOCK_DATA } from "./fixtures.js";

test.beforeEach(async ({ page }) => {
  await setupPage(page);
});

test("app loads and sidebar shows document list", async ({ page }) => {
  await gotoApp(page);
  const items = page.locator("#sidebar-list .sidebar-item");
  await expect(items).toHaveCount(2);
  await expect(items.first()).toHaveText(/First Document/);
  await expect(items.nth(1)).toHaveText(/Second Document/);
});

test("breadcrumb shows 'Work' at root", async ({ page }) => {
  await gotoApp(page);
  const crumb = page.locator("#breadcrumb .breadcrumb-item").first();
  await expect(crumb).toHaveText("Work");
  await expect(crumb).toHaveClass(/breadcrumb-clickable/);
});

test("click document → sections in sidebar, breadcrumb updates", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);

  // Sidebar now shows sections
  const items = page.locator("#sidebar-list .sidebar-item");
  await expect(items).toHaveCount(2);
  await expect(items.first()).toHaveText(/Introduction/);

  // Breadcrumb: Work › First Document
  const crumbs = page.locator("#breadcrumb .breadcrumb-item");
  await expect(crumbs).toHaveCount(2);
  await expect(crumbs.first()).toHaveText("Work");
  await expect(crumbs.nth(1)).toHaveText("First Document");
});

test("click section → editor appears in content", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);
  await navToSection(page);

  await expect(page.locator("#prosemirror-editor")).toBeVisible();
  await expect(page.locator(".ProseMirror")).toBeVisible();
});

test("click 'Work' breadcrumb → back to documents", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);

  // Verify we're at sections level
  await expect(page.locator("#breadcrumb .breadcrumb-item")).toHaveCount(2);

  // Click "Work"
  await page.locator("#breadcrumb .breadcrumb-clickable").first().click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  // Back to documents
  const items = page.locator("#sidebar-list .sidebar-item");
  await expect(items).toHaveCount(2);
  await expect(items.first()).toHaveText(/First Document/);
  await expect(page.locator("#breadcrumb .breadcrumb-item")).toHaveCount(1);
});

test("click intermediate breadcrumb → pops to that level", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);
  await navToSection(page);

  // Breadcrumb: Work › First Document › Introduction
  await expect(page.locator("#breadcrumb .breadcrumb-item")).toHaveCount(3);

  // Click "First Document" breadcrumb (second clickable item)
  await page.locator("#breadcrumb .breadcrumb-clickable").nth(1).click();
  await page.locator("#sidebar-list .sidebar-item").first().waitFor({ state: "visible" });

  // Back to sections level
  await expect(page.locator("#breadcrumb .breadcrumb-item")).toHaveCount(2);
  const items = page.locator("#sidebar-list .sidebar-item");
  await expect(items.first()).toHaveText(/Introduction/);
});

test("add button visible at document level", async ({ page }) => {
  await gotoApp(page);
  await expect(page.locator("#sidebar-actions .sidebar-action-btn")).toBeVisible();
});

test("add button visible at section level", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);
  await expect(page.locator("#sidebar-actions .sidebar-action-btn")).toBeVisible();
});

test("add button hidden during editing", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);
  await navToSection(page);
  await expect(page.locator("#sidebar-actions .sidebar-action-btn")).not.toBeVisible();
});

test("delete button appears on sidebar items", async ({ page }) => {
  await gotoApp(page);
  const delBtn = page.locator("#sidebar-list .sidebar-item .sidebar-delete-btn").first();
  await expect(delBtn).toBeAttached();
});

test("empty list shows 'No items' text", async ({ page }) => {
  // Override the documents route to return empty
  await page.route(`http://127.0.0.1:55555/api/documents`, (route) => {
    route.fulfill({ json: [] });
  });
  await page.goto("http://localhost:5199");
  // Click through picker first (select first recent work)
  await page.locator(".picker-work-item").first().waitFor({ state: "visible", timeout: 5000 });
  await page.locator(".picker-work-item").first().click();
  // Wait for empty state (no sidebar-item will appear, so wait for the empty message)
  await expect(page.locator(".sidebar-empty")).toHaveText("No items");
});

test("content placeholder shows correct hint at document level", async ({ page }) => {
  await gotoApp(page);
  await expect(page.locator(".content-placeholder")).toContainText(
    "Select a document to browse its sections"
  );
});

test("content placeholder shows correct hint at section level", async ({ page }) => {
  await gotoApp(page);
  await navToDocument(page);
  await expect(page.locator(".content-placeholder")).toContainText(
    "Select a section to view its content"
  );
});
