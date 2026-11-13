# Playwright Visual, Console & Zoom Verification Recipes

## 1. Mandatory Error & Network Guard Attachment

```ts
export function attachRuntimeGuards(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const serverErrors: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => pageErrors.push(err.message));
  page.on("response", (res) => {
    if (res.status() >= 500) serverErrors.push(`${res.status()} ${res.url()}`);
  });

  return () => {
    expect(consoleErrors, `Console errors: ${consoleErrors.join("\n")}`).toEqual([]);
    expect(pageErrors, `Uncaught page errors: ${pageErrors.join("\n")}`).toEqual([]);
    expect(serverErrors, `HTTP 5xx errors: ${serverErrors.join("\n")}`).toEqual([]);
  };
}
```

## 2. Desktop Viewport & Zoom Sweep (`80%`, `100%`, `120%`)

```ts
for (const viewport of [
  { width: 1024, height: 768 },
  { width: 1280, height: 800 },
  { width: 1920, height: 1080 },
]) {
  await page.setViewportSize(viewport);
  for (const zoom of ["0.8", "1", "1.2"]) {
    await page.evaluate((z) => { (document.documentElement.style as any).zoom = z; }, zoom);
    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1
    );
    expect(hasHorizontalOverflow, `Overflow at ${viewport.width}px zoom ${zoom}`).toBe(false);
  }
}
```

## 3. Verifying Authoritative Server PDF Export (Never `jsPDF` Blob Hacks)

- Click export trigger inside `Promise.all([page.waitForEvent("download"), exportBtn.click()])`.
- Read downloaded buffer/header via stream and verify magic bytes `%PDF-1.` and non-trivial file size (`> 10 KB`), checking that the HTTP network response originated from backend Chromium generation (`/generate` / `/pdf`) cleanly.

