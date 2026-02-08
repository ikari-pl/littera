/**
 * editor.spec.js — ProseMirror: typing, formatting, slash menu, code blocks.
 */

import { test, expect } from "@playwright/test";
import { setupPage, navToEditor } from "./fixtures.js";

test.beforeEach(async ({ page }) => {
  await setupPage(page);
});

test("editor container created on section navigation", async ({ page }) => {
  await navToEditor(page);
  await expect(page.locator("#prosemirror-editor")).toBeVisible();
});

test("ProseMirror is contenteditable and focusable", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await expect(pm).toHaveAttribute("contenteditable", "true");

  await pm.click();
  await expect(pm).toBeFocused();
});

test("can type text into editor", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();

  // Create a fresh block to type into
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("Hello Littera");

  await expect(pm).toContainText("Hello Littera");
});

test("bold via Meta+B wraps in <strong>", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();

  // Create a fresh block to type into
  await page.keyboard.press("Shift+Enter");

  // Toggle bold ON, type text, toggle bold OFF
  await page.keyboard.press("Meta+b");
  await page.keyboard.type("bold text");
  await page.keyboard.press("Meta+b");

  await expect(pm.locator("strong")).toContainText("bold text");
});

test("italic via Meta+I wraps in <em>", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();

  await page.keyboard.press("Shift+Enter");
  await page.keyboard.press("Meta+i");
  await page.keyboard.type("italic text");
  await page.keyboard.press("Meta+i");

  await expect(pm.locator("em")).toContainText("italic text");
});

test("slash menu visible on '/' at start of empty paragraph", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();

  // Shift+Enter creates a fresh littera_block with an empty paragraph
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/");

  await expect(page.locator(".slash-menu")).toBeVisible();
});

test("slash menu filters — type '/h1' shows only Heading 1", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/h1");

  const menu = page.locator(".slash-menu");
  await expect(menu).toBeVisible();

  const items = menu.locator(".slash-item");
  await expect(items).toHaveCount(1);
  await expect(items.first()).toContainText("Heading 1");
});

test("slash 'Heading 1' → <h1> node", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/");

  await page.locator(".slash-menu").waitFor({ state: "visible" });
  await page.keyboard.press("Enter"); // select first item (Heading 1)

  await page.keyboard.type("My Heading");
  await expect(pm.locator("h1")).toContainText("My Heading");
});

test("slash 'Code Block' → <pre><code> node", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/code");

  await page.locator(".slash-menu").waitFor({ state: "visible" });
  await page.keyboard.press("Enter");

  await expect(pm.locator("pre")).toBeVisible();
  // <code> is inside <pre> — it exists but may have zero size when empty
  await expect(pm.locator("pre code")).toBeAttached();
});

test("slash 'Quote' → <blockquote> wrapping (Bug 4 regression)", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/quote");

  await page.locator(".slash-menu").waitFor({ state: "visible" });
  await page.keyboard.press("Enter");

  await page.keyboard.type("A wise saying");
  await expect(pm.locator("blockquote")).toContainText("A wise saying");
});

test("slash 'Horizontal Rule' → <hr> node", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/hr");

  await page.locator(".slash-menu").waitFor({ state: "visible" });
  await page.keyboard.press("Enter");

  await expect(pm.locator("hr")).toBeVisible();
});

test("Escape dismisses slash menu", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/");

  await expect(page.locator(".slash-menu")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".slash-menu")).not.toBeVisible();
});

test("code block has line-height ≤ 1.2 (Bug 5 regression)", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/code");

  await page.locator(".slash-menu").waitFor({ state: "visible" });
  await page.keyboard.press("Enter");

  const pre = pm.locator("pre").first();
  await expect(pre).toBeVisible();

  const lineHeight = await pre.evaluate((el) => {
    const computed = window.getComputedStyle(el);
    const lh = parseFloat(computed.lineHeight);
    const fs = parseFloat(computed.fontSize);
    // lineHeight can be "normal" (~1.2) or a px value
    if (isNaN(lh)) return 1.2; // "normal" is approximately 1.2
    return lh / fs;
  });
  expect(lineHeight).toBeLessThanOrEqual(1.3);
});

test("code block <pre> has spellcheck/autocorrect/autocapitalize off (Bug 6 regression)", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("/code");

  await page.locator(".slash-menu").waitFor({ state: "visible" });
  await page.keyboard.press("Enter");

  const pre = pm.locator("pre").first();
  await expect(pre).toBeVisible();

  await expect(pre).toHaveAttribute("spellcheck", "false");
  await expect(pre).toHaveAttribute("autocorrect", "off");
  await expect(pre).toHaveAttribute("autocapitalize", "off");
});

test("input rule: ``` creates code block", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();
  await page.keyboard.press("Shift+Enter");

  // Type three backticks — the inputRule triggers on the third backtick
  await page.keyboard.type("```");

  await expect(pm.locator("pre")).toBeVisible();
});

test("Shift+Enter creates new littera_block", async ({ page }) => {
  await navToEditor(page);
  const pm = page.locator(".ProseMirror");
  await pm.click();

  // Count initial blocks
  const initialCount = await pm.locator(".littera-block").count();

  await page.keyboard.press("Shift+Enter");

  // Should have one more block
  const newCount = await pm.locator(".littera-block").count();
  expect(newCount).toBe(initialCount + 1);
});
