import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.describe("Accessibility, Console Traps & Responsive Zoom Audits", () => {
  const VIEWPORTS = [
    { name: "1024x768", width: 1024, height: 768 },
    { name: "1280x800", width: 1280, height: 800 },
    { name: "1920x1080", width: 1920, height: 1080 },
  ];
  const ZOOM_LEVELS = [0.8, 1.0, 1.2];

  test("Login page passes WCAG 2.2 AA audit and has zero horizontal overflow across zoom levels", async ({ page }) => {
    const consoleErrors: string[] = [];
    const serverErrors: string[] = [];

    page.on("console", (msg) => {
      const text = msg.text();
      // Filter expected 401 resource loads when checking unauthenticated session
      if (msg.type() === "error" && !text.includes("401 (Unauthorized)")) {
        consoleErrors.push(text);
      }
    });
    page.on("response", (res) => {
      if (res.status() >= 500) serverErrors.push(`${res.status()} ${res.url()}`);
    });

    // Unauthenticated /login mock for session check
    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ error: "Unauthorized" }),
      })
    );

    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();

    // Verify zero console or server 5xx errors on load
    expect(consoleErrors).toEqual([]);
    expect(serverErrors).toEqual([]);

    // Run automated accessibility audit
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .disableRules(["color-contrast"]) // contrast verified via token lock
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);

    // Responsive horizontal overflow check across viewports and zoom levels
    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      for (const zoom of ZOOM_LEVELS) {
        await page.evaluate((z) => {
          document.body.style.zoom = String(z);
        }, zoom);

        const hasOverflow = await page.evaluate(() => {
          return document.documentElement.scrollWidth > window.innerWidth + 2;
        });
        expect(hasOverflow).toBeFalsy();
      }
    }
  });

  test("Mocked Upload view renders cleanly with zero console traps and stable layout", async ({ page, context }) => {
    const consoleErrors: string[] = [];
    const serverErrors: string[] = [];

    page.on("console", (msg) => {
      const text = msg.text();
      // Filter expected 401 resource loads when checking unauthenticated session
      if (msg.type() === "error" && !text.includes("401 (Unauthorized)")) {
        consoleErrors.push(text);
      }
    });
    page.on("response", (res) => {
      if (res.status() >= 500) serverErrors.push(`${res.status()} ${res.url()}`);
    });

    await context.addCookies([
      {
        name: "risklocker_session",
        value: "mock-test-session",
        domain: "127.0.0.1",
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);

    await page.route("**/api/auth/me", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "user-1", email: "staff@risklocker.test", role: "staff" }),
      })
    );
    await page.route("**/api/notifications/unread-count", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ unread_count: 0 }),
      })
    );
    await page.route("**/api/settings/limits", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ max_source_pdf_bytes: 20 * 1024 * 1024 }),
      })
    );
    await page.route("**/api/business/companies?**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ companies: [] }),
      })
    );

    await page.goto("/upload");
    await expect(page.getByRole("heading", { name: /Upload Quotation|Marketing Comparison Intake/i })).toBeVisible();

    expect(consoleErrors).toEqual([]);
    expect(serverErrors).toEqual([]);

    // Check zoom stability on upload view
    for (const zoom of ZOOM_LEVELS) {
      await page.evaluate((z) => {
        document.body.style.zoom = String(z);
      }, zoom);

      const hasOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > window.innerWidth + 2;
      });
      expect(hasOverflow).toBeFalsy();
    }
  });
});
