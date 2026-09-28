/**
 * reviews.spec.js — Reviews tab and in-place edit.
 */

import { test, expect } from "@playwright/test";
import { setupPage, gotoApp, BASE } from "./fixtures.js";

test.beforeEach(async ({ page }) => {
  await setupPage(page);
});

async function fillAppPrompt(page, value) {
  const dialog = page.locator(".app-dialog").last();
  await dialog.waitFor({ state: "visible" });
  const input = dialog.locator(".app-dialog-input");
  await input.fill(value);
  await dialog.locator('[data-act="ok"]').click();
}

test("edit review from Reviews panel sends PUT", async ({ page }) => {
  await gotoApp(page);

  let putBody = null;
  await page.route(`${BASE}/api/reviews/rev-1`, async (route) => {
    if (route.request().method() === "PUT") {
      putBody = route.request().postDataJSON();
      await route.fulfill({ json: { ok: true } });
      return;
    }
    await route.fallback();
  });

  await page.locator("#tab-reviews").click();
  await page.locator(".review-row").first().waitFor({ state: "visible" });
  await expect(page.locator(".review-description")).toContainText(
    "Needs a stronger opening",
  );
  await page.locator(".review-edit-btn").click();

  await fillAppPrompt(page, "Stronger thesis");
  await fillAppPrompt(page, "high");

  await expect.poll(() => putBody).not.toBeNull();
  expect(putBody).toEqual({
    description: "Stronger thesis",
    severity: "high",
  });
});
