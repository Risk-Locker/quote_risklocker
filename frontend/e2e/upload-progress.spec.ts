import { expect, test } from "@playwright/test";

test("one-file upload shows truthful bounded job progress without a global loading capsule", async ({ page, context }) => {
  let jobPoll = 0;
  const idempotencyKeys: string[] = [];

  await context.addCookies([{
    name: "risklocker_session",
    value: "browser-contract-session",
    domain: "127.0.0.1",
    path: "/",
    httpOnly: true,
    sameSite: "Lax",
  }]);
  await page.route("**/api/auth/me", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ id: "user-1", email: "staff@risklocker.test", role: "staff" }),
  }));
  await page.route("**/api/notifications/unread-count", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ unread_count: 0 }),
  }));
  await page.route("**/api/settings/limits", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ max_source_pdf_bytes: 20 * 1024 * 1024 }),
  }));
  await page.route("**/api/uploads", async (route) => {
    idempotencyKeys.push(await route.request().headerValue("idempotency-key") || "");
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ session_id: "session-1", job_id: "job-1", uploaded_file_id: "file-1", created: true }),
    });
  });
  await page.route("**/api/jobs/job-1", (route) => {
    jobPoll += 1;
    const completed = jobPoll >= 4;
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        job: {
          state: completed ? "completed" : jobPoll === 1 ? "queued" : "processing",
          progress: completed ? 100 : jobPoll * 20,
          phase: completed ? "completed" : jobPoll === 1 ? "queued" : "extracting",
          heartbeat_at: new Date().toISOString(),
          elapsed_seconds: jobPoll * 1.25,
          phase_timestamps: { queued: new Date().toISOString() },
        },
      }),
    });
  });

  await page.goto("/upload");
  await expect(page.getByRole("heading", { name: "Upload quotation PDF" })).toBeVisible();
  await expect(page.getByText(/Loading… \d/)).toHaveCount(0);

  await page.locator('input[type="file"]').setInputFiles({
    name: "quotation.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\n%%EOF"),
  });
  await page.getByRole("button", { name: "Upload quotation PDF" }).click();

  await expect(page.getByRole("status")).toContainText(/Waiting for worker|Reading quotation/);
  await expect(page.getByRole("status")).toContainText(/Elapsed/);
  await expect(page).toHaveURL(/\/sessions\/session-1\/review$/);
  expect(idempotencyKeys).toHaveLength(1);
  expect(idempotencyKeys[0]).toBeTruthy();
});
