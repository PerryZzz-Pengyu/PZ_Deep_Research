import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

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
  await expect(page.locator(".sidebar .job-status")).toHaveText("已完成");
  await expect(page.locator(".report-body")).toContainText("核心结论");
});

test("完成的研究任务会出现在当前访客的历史记录中", async ({ page }) => {
  const query = `验证研究历史 ${Date.now()}`;
  await page.getByLabel("研究问题").fill(query);
  await page.getByRole("button", { name: "开始", exact: true }).click();
  await expect(page.locator(".job-status")).toHaveText("已完成", { timeout: 30_000 });

  await page.getByRole("button", { name: "历史", exact: true }).click();

  await expect(page.getByRole("heading", { name: "研究历史" })).toBeVisible();
  const historyItem = page.getByRole("button", { name: new RegExp(query) });
  await expect(historyItem).toBeVisible();
  await historyItem.click();

  await expect(page.getByRole("heading", { name: "报告详情" })).toBeVisible();
  await expect(page.getByRole("heading", { name: query })).toBeVisible();
  await expect(page.locator(".sidebar .job-status")).toHaveText("已完成");
  await expect(page.locator(".report-body")).toContainText("核心结论");
});

test("可以从报告详情重新运行并创建独立任务", async ({ page }) => {
  const query = `验证重新运行 ${Date.now()}`;
  await page.getByLabel("研究问题").fill(query);
  await page.getByRole("button", { name: "开始", exact: true }).click();
  await expect(page.locator(".job-status")).toHaveText("已完成", { timeout: 30_000 });
  const originalJobId = await page.locator(".job-id-text").textContent();

  await page.getByRole("button", { name: "历史", exact: true }).click();
  await page.getByRole("button", { name: new RegExp(query) }).click();
  await expect(page.getByRole("heading", { name: "报告详情" })).toBeVisible();
  await page.getByRole("button", { name: "重新运行", exact: true }).click();

  await expect(page.getByLabel("研究问题")).toHaveValue(query);
  await expect(page.locator(".job-id-text")).not.toHaveText(originalJobId || "");
  await expect(page.locator(".job-status")).toHaveText(/研究中|已完成/);
  await expect(page.locator(".job-status")).toHaveText("已完成", { timeout: 30_000 });
  await expect(page.locator(".report-body")).toContainText("核心结论");
});

test("可以将当前报告导出为 Markdown 文件", async ({ page }) => {
  const query = "验证 Markdown 导出 / 文件名";
  await expect(page.getByRole("button", { name: "导出 Markdown", exact: true })).toBeDisabled();
  await page.getByLabel("研究问题").fill(query);
  await page.getByRole("button", { name: "开始", exact: true }).click();
  await expect(page.locator(".job-status")).toHaveText("已完成", { timeout: 30_000 });
  await page.getByRole("button", { name: "历史", exact: true }).click();
  await page.getByRole("button", { name: new RegExp(query) }).click();
  await expect(page.getByRole("heading", { name: "报告详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "导出 Markdown", exact: true })).toBeEnabled();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 Markdown", exact: true }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toBe("验证-Markdown-导出-文件名.md");
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const content = await readFile(downloadPath!, "utf8");
  expect(content).toContain("## 核心结论");
  expect(content).toContain("PZ Deep Research");
  expect(content.endsWith("\n")).toBe(true);
});

test("可以从报告详情导出正式 PDF 文件", async ({ page }) => {
  const query = "验证 PDF 导出 / 文件名";
  await expect(page.getByRole("button", { name: "导出 PDF", exact: true })).toBeDisabled();
  await page.getByLabel("研究问题").fill(query);
  await page.getByRole("button", { name: "开始", exact: true }).click();
  await expect(page.locator(".job-status")).toHaveText("已完成", { timeout: 30_000 });
  await page.getByRole("button", { name: "历史", exact: true }).click();
  await page.getByRole("button", { name: new RegExp(query) }).click();
  await expect(page.getByRole("heading", { name: "报告详情" })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 PDF", exact: true }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toBe("验证-PDF-导出-文件名.pdf");
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const content = await readFile(downloadPath!);
  expect(content.subarray(0, 5).toString("ascii")).toBe("%PDF-");
  expect(content.subarray(-1024).toString("latin1")).toContain("%%EOF");
  expect(content.length).toBeGreaterThan(8_000);
});
