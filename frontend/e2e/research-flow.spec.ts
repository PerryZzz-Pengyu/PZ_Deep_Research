import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
  await expect(page.getByLabel("研究问题")).toBeEnabled();
  await page.getByLabel("模型 Provider").selectOption("mock");
  await page.getByRole("tab", { name: /快速/ }).click();
});

test("可以取消运行中的研究任务并保留当前进度", async ({ page }) => {
  await page.getByLabel("研究问题").fill("验证研究任务取消功能");
  await page.getByRole("button", { name: "开始", exact: true }).click();

  await expect(page.locator(".job-id-text")).not.toHaveText("尚未创建");
  await expect(page.getByRole("button", { name: "停止", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "停止", exact: true }).click();

  await expect(page.locator(".job-status")).toHaveText("已取消");
  await expect(page.getByText("研究任务已取消", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始", exact: true })).toBeEnabled();
});

test("刷新页面后恢复运行任务，并在完成后恢复报告", async ({ page }) => {
  const query = "验证刷新页面后的任务恢复功能";
  await page.getByLabel("研究问题").fill(query);
  await page.getByRole("button", { name: "开始", exact: true }).click();

  const jobId = page.locator(".job-id-text");
  await expect(jobId).not.toHaveText("尚未创建");
  const persistedJobId = await jobId.textContent();

  await page.reload();

  await expect(page.getByLabel("研究问题")).toHaveValue(query);
  await expect(jobId).toHaveText(persistedJobId || "");
  await expect(page.locator(".job-status")).toHaveText(/研究中|已完成/);
  await expect(page.locator(".job-status")).toHaveText("已完成", { timeout: 30_000 });
  await expect(page.getByText("研究报告已生成", { exact: true })).toBeVisible();
  await expect(page.locator(".report-body")).toContainText("核心结论");

  await page.reload();

  await expect(jobId).toHaveText(persistedJobId || "");
  await expect(page.locator(".job-status")).toHaveText("已完成");
  await expect(page.locator(".report-body")).toContainText("核心结论");
});
