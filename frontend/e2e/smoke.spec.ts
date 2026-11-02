import { test, expect } from "@playwright/test";

test("dashboard loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Linux System Health Dashboard" })).toBeVisible();
});

test("dashboard displays core metric cards", async ({ page }) => {
  await page.goto("/");
  for (const name of ["CPU", "Memory", "Disk", "Network"]) {
    await expect(page.getByRole("article", { name: `${name} metric` })).toBeVisible();
  }
});

test("theme toggle switches themes", async ({ page }) => {
  await page.goto("/");
  const button = page.getByRole("button", { name: /Theme switch/i });
  await expect(button).toBeVisible();
  const before = (await button.textContent())?.trim() ?? "";
  await button.click();
  const after = (await button.textContent())?.trim() ?? "";
  expect(before).not.toBe(after);
});

