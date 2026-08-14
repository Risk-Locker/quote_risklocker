import { expect, test } from "@playwright/test";
import path from "node:path";
import { writeFile } from "node:fs/promises";

test("Template Builder behaviors work in an isolated browser at fit and non-100% zoom", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const consoleErrors: string[] = [];
  const failedResponses: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("response", (response) => { if (response.status() >= 400) failedResponses.push(`${response.status()} ${response.url()}`); });
  const templateId = "e2e-template";
  let mockTemplate = {
    id: templateId,
    revision: 1,
    name: "E2E Builder",
    insurance_type: "Motor",
    status: "active",
    locked: false,
    fixed_fields: {
      version: 7,
      page_profile: { profile_key: "a4", name: "A4", width: 794, height: 1123, unit: "px", safe_margins: { top: 24, right: 24, bottom: 24, left: 24 } },
      variables: [{ id: "customer_name", label: "Customer Name", type: "text", source: "field", field: "customer_name" }],
      cards: {}, packages: [], assets: {}, canvas: { width: 794, height: 1123, elements: [] as Array<Record<string, unknown>> },
    },
  };
  await page.context().addCookies([{ name: "risklocker_session", value: "e2e-session", domain: "127.0.0.1", path: "/" }]);
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: { id: "e2e-user", email: "admin@risklocker.local", role: "super_admin", status: "active" } }));
  await page.route(`**/api/admin/templates/${templateId}`, async (route) => {
    if (route.request().method() === "PATCH") {
      const body = route.request().postDataJSON();
      mockTemplate = { ...mockTemplate, ...body, revision: mockTemplate.revision + 1 };
    }
    await route.fulfill({ json: { template: mockTemplate } });
  });
  await page.route("**/api/business/assets?**", (route) => route.fulfill({ json: { assets: { items: [], page: 1, page_size: 100, total: 0 } } }));
  await page.route("**/api/business/template-page-profiles", (route) => route.fulfill({ json: { page_profiles: [mockTemplate.fixed_fields.page_profile, { profile_key: "extended_portrait", name: "Extended Portrait", width: 794, height: 1480, unit: "px", safe_margins: { top: 32, right: 28, bottom: 32, left: 28 } }] } }));
  await page.route("**/api/admin/template-assets", (route) => route.fulfill({ json: { assets: [], total: 0, folders: [] } }));
  const evidence: Record<string, unknown> = {};

  {
    consoleErrors.length = 0;
    failedResponses.length = 0;
    const started = performance.now();
    await page.goto(`/builder/templates/${templateId}/builder`);
    if ((page.viewportSize()?.width || 0) < 1024) {
      await expect(page.getByRole("heading", { name: "Canvas editing needs a wider screen" })).toBeVisible();
      await expect(page.getByTestId("template-canvas")).toBeHidden();
      evidence.ready_ms = Math.round(performance.now() - started);
      evidence.canvas_width_gate = true;
      expect(consoleErrors).toEqual([]);
      expect(failedResponses).toEqual([]);
      return;
    }
    await expect(page.getByRole("heading", { name: "Layers", exact: true })).toBeVisible();
    await expect(page.getByTestId("template-canvas")).toBeVisible();
    evidence.ready_ms = Math.round(performance.now() - started);

    const zoomOutput = page.locator('footer[aria-label="Canvas view controls"] output');
    await expect(zoomOutput).toHaveText(/%$/);
    await expect.poll(async () => Number((await zoomOutput.textContent())?.replace("%", ""))).toBeLessThan(100);
    const scenario = page.getByRole("combobox", { name: "Scenario", exact: true });
    await expect(scenario.locator('option[value="20"]')).toHaveCount(1);
    await expect(scenario.locator('option[value="100"]')).toHaveCount(0);
    await expect(page.getByText("Our Specials", { exact: true })).toHaveCount(0);

    for (const name of ["Rectangle", "Ellipse", "Triangle", "Diamond", "Line", "Text", "Variable", "Image", "Current benefits", "Available add-ons"]) {
      await page.getByRole("button", { name, exact: true }).last().click();
    }
    const layers = page.getByRole("region", { name: "Template layers" });
    for (const name of ["Rectangle", "Ellipse", "Triangle", "Diamond", "Line", "Text block", "Current Benefits", "Available Add-ons"]) {
      await expect(layers.getByText(name, { exact: true }).first()).toBeVisible();
    }
    const triangle = page.locator('[data-element-id^="triangle_"]').last();
    await expect(triangle).toHaveCSS("clip-path", /polygon/);

    await layers.getByRole("button", { name: "Rectangle", exact: true }).first().dblclick();
    const rename = layers.locator("input").first();
    await rename.fill("Pricing panel");
    await rename.press("Enter");
    await expect(layers.getByText("Pricing panel", { exact: true })).toBeVisible();

    const pricingLayer = layers.getByRole("button", { name: "Pricing panel", exact: true });
    await pricingLayer.click();
    await page.getByRole("button", { name: "Front", exact: true }).click();
    const xInput = page.getByLabel("x", { exact: true });
    const initialX = Number(await xInput.inputValue());
    await page.getByRole("button", { name: "Fit selection" }).click();
    await expect.poll(async () => Number((await zoomOutput.textContent())?.replace("%", ""))).toBeGreaterThan(100);
    await page.getByLabel("Canvas zoom").fill("0.5");
    const pricingNode = page.getByTestId("template-canvas").getByRole("button", { name: "Pricing panel", exact: true });
    const pricingBox = await pricingNode.boundingBox();
    if (!pricingBox) throw new Error("Pricing rectangle has no canvas bounds.");
    await page.mouse.move(pricingBox.x + pricingBox.width / 2, pricingBox.y + pricingBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(pricingBox.x + pricingBox.width / 2 + 40, pricingBox.y + pricingBox.height / 2 + 20, { steps: 8 });
    await page.mouse.up();
    expect(Number(await xInput.inputValue())).toBeGreaterThan(initialX + 50);

    const resizeHandle = pricingNode.getByRole("button", { name: /Resize Pricing panel from se/ });
    const beforeResize = await pricingNode.boundingBox();
    const handleBox = await resizeHandle.boundingBox();
    if (!beforeResize || !handleBox) throw new Error("Resize handle is missing.");
    await page.mouse.move(handleBox.x + handleBox.width / 2, handleBox.y + handleBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(handleBox.x + 35, handleBox.y + 20, { steps: 6 });
    await page.mouse.up();
    const afterResize = await pricingNode.boundingBox();
    expect(afterResize?.width).toBeGreaterThan(beforeResize.width);

    const opacity = page.getByLabel("Opacity slider");
    await opacity.focus();
    await opacity.press("Home");
    await expect(page.getByLabel("Opacity value")).toHaveValue("0");
    await page.getByRole("group", { name: "Opacity" }).getByRole("button", { name: "Reset" }).click();
    await expect(page.getByLabel("Opacity value")).toHaveValue("1");

    const margins = page.getByRole("group", { name: "Safe margins (px)" });
    await margins.getByLabel("top", { exact: true }).fill("36");
    await margins.getByLabel("right", { exact: true }).fill("28");
    await expect(margins.getByLabel("top", { exact: true })).toHaveValue("36");

    const ruler = page.getByTestId("horizontal-ruler");
    const rulerBox = await ruler.boundingBox();
    const canvasBox = await page.getByTestId("template-canvas").boundingBox();
    if (!rulerBox || !canvasBox) throw new Error("Canvas rulers are missing.");
    await page.mouse.move(rulerBox.x + 120, rulerBox.y + rulerBox.height / 2);
    await page.mouse.down();
    await page.mouse.move(canvasBox.x + 120, canvasBox.y + 90, { steps: 5 });
    await page.mouse.up();
    const verticalGuide = page.getByRole("button", { name: /Vertical guide at/ });
    await expect(verticalGuide).toHaveCount(1);
    await verticalGuide.click();
    await page.keyboard.press("Delete");
    await expect(verticalGuide).toHaveCount(0);

    await pricingNode.click({ button: "right" });
    await expect(page.getByRole("menu", { name: "Canvas layer actions" })).toBeVisible();
    await page.getByRole("menuitem", { name: "Duplicate" }).click();
    await expect(layers.getByText(/Pricing panel copy/)).toBeVisible();

    await layers.getByRole("button", { name: "Pricing panel", exact: true }).click();
    await layers.getByRole("button", { name: "Ellipse", exact: true }).first().click({ modifiers: ["Shift"] });
    await layers.getByRole("button", { name: "Ellipse", exact: true }).first().click({ button: "right" });
    await page.getByRole("menuitem", { name: "Group selection" }).click();
    const groupName = await page.getByLabel("Group name").inputValue();
    await expect(layers.getByText(groupName, { exact: true }).first()).toBeVisible();
    await layers.getByRole("button", { name: groupName, exact: true }).click({ button: "right" });
    await page.getByRole("menuitem", { name: "Ungroup" }).click();
    await expect(layers.getByText(groupName, { exact: true })).toHaveCount(0);

    await layers.getByRole("button", { name: "Ellipse", exact: true }).first().click();
    await layers.getByRole("button", { name: "Hide Ellipse" }).first().click();
    await expect(page.getByTestId("template-canvas").locator('[data-element-id^="ellipse_"]')).toHaveCount(0);
    await layers.getByRole("button", { name: "Show Ellipse" }).first().click();
    await expect(page.getByTestId("template-canvas").locator('[data-element-id^="ellipse_"]')).toHaveCount(1);
    await layers.getByRole("button", { name: "Lock Ellipse" }).first().click();
    await expect(layers.getByRole("button", { name: "Unlock Ellipse" }).first()).toBeVisible();

    const templateName = page.locator('main > div').first().getByRole("textbox").first();
    const beforeName = await templateName.inputValue();
    await templateName.fill(`${beforeName} changed`);
    await templateName.press("Control+z");
    await expect(templateName).toHaveValue(beforeName);

    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Template draft saved.")).toBeVisible();
    await page.reload();
    await expect(layers.getByText("Pricing panel", { exact: true })).toBeVisible();
    await expect(page.getByRole("group", { name: "Safe margins (px)" }).getByLabel("top", { exact: true })).toHaveValue("36");

    await page.getByRole("button", { name: "Diamond", exact: true }).last().click();
    await page.getByRole("button", { name: "Templates", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Unsaved template changes" })).toBeVisible();
    await page.getByRole("button", { name: "Keep editing" }).click();
    await expect(page).toHaveURL(new RegExp(`/builder/templates/${templateId}/builder`));

    await page.screenshot({ path: path.resolve("../.qc-tmp/screens/template-builder-functional-1440.png"), fullPage: true });
    evidence.layer_count = await layers.locator('[draggable="true"]').count();
    evidence.final_zoom = await zoomOutput.textContent();
    evidence.console_errors = consoleErrors;
    evidence.failed_responses = failedResponses;
    expect(consoleErrors).toEqual([]);
    expect(failedResponses).toEqual([]);
    await writeFile(path.resolve("../.qc-tmp/template-builder-functional.json"), JSON.stringify(evidence, null, 2), "utf8");
    await testInfo.attach("template-builder-functional", { body: JSON.stringify(evidence, null, 2), contentType: "application/json" });
  }
});
