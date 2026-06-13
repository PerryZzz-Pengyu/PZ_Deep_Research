import { expect, test, type Page } from "@playwright/test";

const CLERK_REQUEST = /clerk\.accounts\.dev/;
const WORKBENCH_QUERY = /输入一个研究问题|Ask a research question/;
const isolatedBackendPort = process.env.PLAYWRIGHT_BACKEND_PORT;

async function blockClerk(page: Page) {
  await page.route(CLERK_REQUEST, (route) => route.abort("internetdisconnected"));
  if (isolatedBackendPort && isolatedBackendPort !== "8000") {
    await page.route("http://localhost:8000/**", (route) => {
      const url = route.request().url().replace("http://localhost:8000", `http://127.0.0.1:${isolatedBackendPort}`);
      return route.continue({ url });
    });
  }
}

test("marketing interactions remain usable when Clerk cannot initialize", async ({ page }) => {
  await blockClerk(page);
  await page.goto("/");

  const expertMode = page.getByRole("tab", { name: /专家|Expert/, exact: true });
  await expect(expertMode).toBeEnabled();
  await expertMode.click();
  await expect(expertMode).toHaveAttribute("aria-selected", "true");

  const languageButton = page.getByRole("button", { name: "EN", exact: true });
  await languageButton.click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("workbench falls back to guest mode when Clerk cannot initialize", async ({ page }) => {
  await blockClerk(page);
  await page.goto("/workbench");

  const query = page.getByPlaceholder(WORKBENCH_QUERY);
  await expect(query).toBeEnabled({ timeout: 7_000 });
  await expect(page.getByText(/访客模式|Guest mode/, { exact: true })).toBeVisible();

  const expertMode = page.getByRole("tab", { name: /专家|Expert/, exact: true });
  await expertMode.click();
  await expect(expertMode).toHaveAttribute("aria-selected", "true");
});

test("a hanging job restore cannot permanently lock research submission", async ({ page }) => {
  await blockClerk(page);
  await page.addInitScript(() => {
    window.localStorage.setItem("pz-deep-research-active-job", "stale-job");
  });
  await page.route("**/api/research-jobs/stale-job", async () => {
    await new Promise((resolve) => setTimeout(resolve, 30_000));
  });
  await page.route("**/api/research-jobs/stale-job/events", async () => {
    await new Promise((resolve) => setTimeout(resolve, 30_000));
  });

  await page.goto("/workbench");

  const query = page.getByPlaceholder(WORKBENCH_QUERY);
  await expect(query).toBeEnabled({ timeout: 7_000 });
  await query.fill("Verify the fail-open research path");
  await expect(page.getByRole("button", { name: /开始研究|Start research/, exact: true })).toBeEnabled();
});

test("community edition forwards a bring-your-own API key without persisting it", async ({ page }) => {
  await blockClerk(page);
  await page.addInitScript(() => {
    window.localStorage.setItem("pz-deep-research-locale", "en");
  });

  // Community-style model options: client selection enabled, OpenAI default.
  await page.route("**/api/models", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        selection_enabled: true,
        routing_version: "community",
        providers: {
          mock: [{ id: "", label: "Dev mode" }],
          openai: [{ id: "gpt-5.4-mini", label: "gpt-5.4-mini" }],
          anthropic: [{ id: "claude-sonnet-4-6", label: "claude-sonnet-4-6" }],
          gemini: [{ id: "gemini-3.5-flash", label: "gemini-3.5-flash" }],
        },
        defaults: { provider: "openai", openai: "gpt-5.4-mini", anthropic: null, gemini: null },
      }),
    });
  });

  let capturedBody: Record<string, unknown> | null = null;
  await page.route("**/api/research-jobs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    capturedBody = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "byok-job",
        rerun_of_job_id: null,
        query: capturedBody?.query,
        mode: capturedBody?.mode,
        provider: "openai",
        model: "gpt-5.4-mini",
        status: "queued",
        draft_report: "",
        final_report: null,
        error: null,
        error_code: null,
        error_retryable: false,
        error_stage: null,
        created_at: "2026-06-13T12:00:00Z",
        updated_at: "2026-06-13T12:00:00Z",
      }),
    });
  });
  await page.route("**/api/research-jobs/byok-job/events", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.route("**/api/research-jobs/byok-job/stream**", (route) =>
    route.fulfill({ status: 200, contentType: "text/event-stream", body: "" }));

  await page.goto("/workbench");
  const query = page.getByPlaceholder(/Ask a research question/);
  await expect(query).toBeEnabled({ timeout: 7_000 });

  // Selection is enabled, so the advanced panel and the BYOK key field are present.
  await page.getByRole("button", { name: "Advanced options", exact: true }).click();
  const keyInput = page.locator("#adv-api-key");
  await expect(keyInput).toBeVisible();
  const userKey = "sk-user-playwright-byok-1234567890";
  await keyInput.fill(userKey);

  await query.fill("Verify BYOK key forwarding");
  await page.getByRole("button", { name: "Start research", exact: true }).click();

  await expect.poll(() => capturedBody?.api_key).toBe(userKey);
  expect(capturedBody?.provider).toBe("openai");

  // The key lives only in component memory and must never be written to storage.
  const leaked = await page.evaluate((needle) => {
    const probe = (store: Storage) =>
      Object.keys(store).some((key) => (store.getItem(key) || "").includes(needle));
    return probe(window.localStorage) || probe(window.sessionStorage);
  }, userKey);
  expect(leaked).toBe(false);
});

test("mobile sources open in a dismissable HeroUI modal", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await blockClerk(page);
  await page.addInitScript(() => {
    window.localStorage.setItem("pz-deep-research-locale", "en");
  });
  await page.goto("/workbench");

  await page.getByRole("tab", { name: "Quick", exact: true }).click();
  await page.getByPlaceholder(/Ask a research question/).fill("Verify mobile source modal");
  await page.getByRole("button", { name: "Start research", exact: true }).click();
  await expect(page.locator(".job-status")).toHaveText("Completed", { timeout: 30_000 });

  await page.getByRole("button", { name: "Sources", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { name: "Sources" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});
