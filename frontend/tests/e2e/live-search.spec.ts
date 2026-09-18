import { expect, test } from "@playwright/test";

test("bus: live search stays editable and never exposes placeholder sellers", async ({ page }) => {
  await page.goto("/?mode=bus");

  const origin = page.getByRole("combobox", { name: "مبدا" });
  await origin.fill("تهران");
  await page.getByRole("option").filter({ hasText: "تهران" }).first().click();

  const destination = page.getByRole("combobox", { name: "مقصد" });
  await destination.fill("اصفهان");
  await page.getByRole("option").filter({ hasText: "اصفهان" }).first().click();

  await page.getByRole("button", { name: "جستجو" }).click();
  await page.waitForURL(/\/results\?/, { timeout: 90_000 });

  const offersArea = page.locator(".offers-area");
  await expect(offersArea).toHaveAttribute("aria-busy", "false", { timeout: 90_000 });
  await expect(page.locator("body")).not.toContainText("example.com");
  await expect(page.locator("body")).not.toContainText(/starcom|compare five|bad compare/i);

  const seatSelectionCard = page.locator("article.offer-card").filter({ hasText: "انتخاب صندلی" }).first();
  await expect(seatSelectionCard).toBeVisible();
  await seatSelectionCard.getByRole("link", { name: "مقایسه فروشنده‌ها" }).click();
  await expect(page.getByRole("heading", { name: "مقایسه فروشنده‌ها" })).toBeVisible();
  await page.getByRole("button", { name: "نقشه صندلی" }).click();
  const seatMapDialog = page.getByRole("dialog", { name: "نقشه صندلی" });
  await expect(seatMapDialog).toBeVisible();
  await expect(seatMapDialog.getByRole("listitem").first()).toBeVisible();
  for (const width of [320, 900, 901, 1100, 1440]) {
    await page.setViewportSize({ width, height: width === 320 ? 800 : 900 });
    const bounds = await seatMapDialog.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    await expect.poll(() => page.evaluate(() => (
      document.documentElement.scrollWidth <= document.documentElement.clientWidth
    ))).toBe(true);
  }
  await page.getByRole("button", { name: "بستن پنجره" }).click();
  await page.goBack();
  await expect(offersArea).toHaveAttribute("aria-busy", "false", { timeout: 90_000 });

  const originalDate = new URL(page.url()).searchParams.get("date");
  const nearbyDate = page.locator(".results-workspace__date-button:not([aria-current=\"date\"]):not(:disabled)").first();
  await expect(nearbyDate).toBeVisible();
  await nearbyDate.click();
  await expect.poll(() => new URL(page.url()).searchParams.get("date")).not.toBe(originalDate);
  await expect(offersArea).toHaveAttribute("aria-busy", "false", { timeout: 90_000 });

  const searchForm = page.getByRole("form", { name: "جزئیات جست‌وجو" });
  await expect(searchForm.getByRole("combobox", { name: "مقصد" })).toHaveValue("اصفهان");
  await expect(searchForm.getByRole("button", { name: "جستجو", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "ویرایش جست‌وجو" })).toHaveCount(0);

  const previousSearchId = new URL(page.url()).searchParams.get("search_id");
  await searchForm.getByRole("button", { name: "جستجو", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("search_id")).not.toBe(previousSearchId);
  await expect(offersArea).toHaveAttribute("aria-busy", "false", { timeout: 90_000 });
  await expect(page.locator(".offer-card").first()).toBeVisible();
  await expect(page.locator("body")).not.toContainText("example.com");
});

test("expired offer renders a Persian recovery path", async ({ page }) => {
  await page.goto("/offers/not-a-real-offer");
  await expect(page.getByRole("heading", { name: "این نتیجه دیگر تازه نیست" })).toBeVisible();
  await expect(page.getByRole("link", { name: "جست‌وجوی دوباره" })).toHaveAttribute("href", "/");
  for (const width of [320, 360, 390, 414, 760, 761, 800, 900, 901, 935, 1024, 1100, 1280, 1440]) {
    await page.setViewportSize({ width, height: width <= 414 ? 844 : 900 });
    await expect.poll(() => page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))).toEqual({ clientWidth: width, scrollWidth: width });
  }
});
