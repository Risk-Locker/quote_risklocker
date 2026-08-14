import { expect, test } from "@playwright/test";
import path from "node:path";
import { writeFile } from "node:fs/promises";


test("company-first Business Setup and supplied assets render without runtime errors", async ({ page }, testInfo) => {
  const consoleErrors: string[] = [];
  const failedResponses: string[] = [];
  const requestStarted = new Map<string, number>();
  const apiTimings: Array<{ url: string; status: number; duration_ms: number }> = [];

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("request", (request) => requestStarted.set(request.url(), Date.now()));
  page.on("response", (response) => {
    const started = requestStarted.get(response.url());
    if (response.url().includes("/api/") && started) {
      apiTimings.push({ url: new URL(response.url()).pathname, status: response.status(), duration_ms: Date.now() - started });
    }
    if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`);
  });

  await page.goto("/login");
  await page.getByLabel("Email").fill(process.env.E2E_EMAIL || "admin@risklocker.local");
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD || "admin123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/upload$/);

  consoleErrors.length = 0;
  failedResponses.length = 0;
  apiTimings.length = 0;
  const benefitsStarted = Date.now();
  await page.goto("/builder/benefits");
  await expect(page.getByRole("heading", { name: "Benefits", exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Builder sections" }).getByRole("link")).toHaveText([
    "Templates",
    "Benefits",
    "Asset Library",
  ]);
  await expect(page.getByText("Our Specials", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("complementary", { name: "Companies" }).getByRole("button")).toHaveCount(9);
  await expect.poll(async () => page.getByRole("complementary", { name: "Companies" }).locator("img").evaluateAll((images) => images.filter((image) => (image as HTMLImageElement).naturalWidth > 0).length)).toBe(8);
  const benefitsReadyMs = Date.now() - benefitsStarted;
  await page.screenshot({ path: path.resolve("../.qc-tmp/screens/business-setup-1440.png"), fullPage: true });

  const templatesStarted = Date.now();
  await page.getByRole("link", { name: "Templates" }).click();
  await expect(page).toHaveURL(/\/builder\/templates$/);
  await expect(page.getByRole("heading", { name: "Templates", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "New group" })).toHaveCount(0);
  await expect(page.locator("article")).not.toHaveCount(0);
  await expect(page.locator("article svg").first()).toBeVisible();
  const templatesReadyMs = Date.now() - templatesStarted;
  await page.screenshot({ path: path.resolve("../.qc-tmp/screens/templates-gallery-1440.png"), fullPage: true });

  const assetsStarted = Date.now();
  await page.getByRole("link", { name: "Asset Library" }).click();
  await expect(page).toHaveURL(/\/builder\/assets$/);
  await page.waitForTimeout(2_000);
  if (await page.getByRole("heading", { name: "Asset Library", exact: true }).count() === 0) {
    throw new Error(JSON.stringify({ url: page.url(), consoleErrors, failedResponses }, null, 2));
  }
  await expect(page.getByRole("heading", { name: "Asset Library", exact: true })).toBeVisible();
  await expect(page.getByText("43 assets", { exact: true })).toBeVisible();
  await expect(page.getByText(/Local \(41\)/)).toHaveCount(0);
  await expect(page.locator("article img")).toHaveCount(43);
  await page.locator("article img").last().scrollIntoViewIfNeeded();
  await expect.poll(async () => page.locator("article img").evaluateAll((images) => images.filter((image) => (image as HTMLImageElement).complete).length)).toBe(43);
  const brokenAssets = await page.locator("article img").evaluateAll((images) => images
    .filter((image) => !(image as HTMLImageElement).naturalWidth)
    .map((image) => ({ alt: image.getAttribute("alt"), src: (image as HTMLImageElement).src })));
  expect(brokenAssets).toEqual([]);
  const assetsReadyMs = Date.now() - assetsStarted;
  await page.screenshot({ path: path.resolve("../.qc-tmp/screens/asset-library-1440.png"), fullPage: true });

  const aliasesStarted = Date.now();
  await page.goto("/settings/extraction/companies");
  await expect(page.getByRole("heading", { name: "Company Detection" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("Our Specials", { exact: true })).toHaveCount(0);
  const aliasesReadyMs = Date.now() - aliasesStarted;
  await page.screenshot({ path: path.resolve("../.qc-tmp/screens/company-detection-1440.png"), fullPage: true });

  expect(failedResponses).toEqual([]);
  expect(consoleErrors).toEqual([]);
  const timingEvidence = JSON.stringify({ benefitsReadyMs, templatesReadyMs, assetsReadyMs, aliasesReadyMs, apiTimings }, null, 2);
  await writeFile(path.resolve("../.qc-tmp/business-setup-timings.json"), timingEvidence, "utf8");
  await testInfo.attach("business-setup-timings", {
    body: timingEvidence,
    contentType: "application/json",
  });
});
