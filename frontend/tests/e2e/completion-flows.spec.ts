import { expect, Page, test } from "@playwright/test";

function dateInTehran(daysFromToday: number) {
  const value = new Date(Date.now() + daysFromToday * 86_400_000);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

async function selectCity(page: Page, label: "مبدا" | "مقصد", query: string, city: string) {
  const input = page.getByRole("combobox", { name: label });
  await input.fill(query);
  await page.getByRole("option").filter({ hasText: city }).first().click();
  await expect(input).toHaveValue(city);
}

async function findLiveTrainDate(page: Page) {
  for (let offset = 1; offset <= 5; offset += 1) {
    const departureDate = dateInTehran(offset);
    const response = await page.request.post("/api/travel/search", {
      data: {
        mode: "train",
        origin: "تهران",
        destination: "قم",
        departure_date: departureDate,
        passengers: { adults: 1, children: 0, infants: 0 },
        preferences: {
          mode: "train",
          exclusive_compartment: false,
          passenger_type: "family",
          vehicle_transport: false,
        },
        intent: "best",
      },
      timeout: 30_000,
    });
    if (!response.ok()) continue;
    const body = await response.json();
    if (body.providers_succeeded > 0 && body.total > 0) return departureDate;
  }
  return null;
}

async function chooseDepartureDate(page: Page, targetDate: string) {
  await page.getByRole("button", { name: "انتخاب تاریخ رفت" }).click();
  const dialog = page.getByRole("dialog", { name: "انتخاب تاریخ" });
  await expect(dialog).toBeVisible();

  const dateButton = dialog.locator(`button[data-date="${targetDate}"]`);
  // Select by the exact ISO value; Persian day numbers repeat across adjacent
  // months. The shared calendar opens on today, so live future dates can only
  // require forward navigation.
  for (let monthOffset = 0; monthOffset < 3 && await dateButton.count() === 0; monthOffset += 1) {
    await dialog.getByRole("button", { name: "ماه بعد" }).click();
  }
  await expect(dateButton).toBeEnabled();
  await dateButton.click();
}

test("flight: live form, seller details, refund rules, and safe redirect stay connected", async ({ page }) => {
  await page.goto("/?mode=flight");
  await selectCity(page, "مبدا", "ته", "تهران");
  await selectCity(page, "مقصد", "مش", "مشهد");
  await page.getByRole("button", { name: "جستجو", exact: true }).click();
  await page.waitForURL(/\/results\?/);

  const offersArea = page.locator(".offers-area");
  await expect(offersArea).toHaveAttribute("aria-busy", "false", { timeout: 90_000 });
  await expect(page.getByRole("heading", { name: /گزینه پرواز/ })).toBeVisible();
  await expect(page.locator("article.offer-card").first()).toBeVisible();

  await page.locator("article.offer-card").first().getByRole("link", { name: "مقایسه فروشنده‌ها" }).click();
  await expect(page.getByRole("heading", { name: "مقایسه فروشنده‌ها" })).toBeVisible();

  for (const width of [320, 360, 390, 414, 760, 761, 800, 900, 901, 935, 1024, 1100, 1280, 1440]) {
    await page.setViewportSize({ width, height: width <= 414 ? 844 : 900 });
    await expect.poll(() => page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))).toEqual({ clientWidth: width, scrollWidth: width });
    await expect(page.locator(".seller-list-card")).toBeVisible();
    await expect(page.locator(".seller-row").first()).toBeVisible();
  }

  for (const width of [320, 761, 935, 1440]) {
    await page.setViewportSize({ width, height: width === 320 ? 800 : 900 });
    await page.getByRole("button", { name: "جزئیات", exact: true }).first().click();
    const detailsDialog = page.getByRole("dialog", { name: "جزئیات بلیت" });
    await expect(detailsDialog).toBeVisible();
    const bounds = await detailsDialog.boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    await page.getByRole("button", { name: "بستن پنجره" }).click();
  }

  for (const width of [320, 900, 901, 1100, 1440]) {
    await page.setViewportSize({ width, height: width === 320 ? 800 : 900 });
    await page.getByRole("button", { name: "قوانین استرداد", exact: true }).first().click();
    const refundDialog = page.getByRole("dialog", { name: "قوانین استرداد" });
    await expect(refundDialog).toBeVisible();
    const refundBounds = await refundDialog.boundingBox();
    expect(refundBounds).not.toBeNull();
    expect(refundBounds!.x).toBeGreaterThanOrEqual(0);
    expect(refundBounds!.x + refundBounds!.width).toBeLessThanOrEqual(width);
    await page.getByRole("button", { name: "بستن پنجره" }).click();

    await page.getByRole("button", { name: "مشاهده در فروشگاه" }).first().click();
    const redirectDialog = page.getByRole("dialog", { name: "بررسی در سایت فروشنده" });
    await expect(redirectDialog).toContainText("قیمت، موجودی و جزئیات بلیت را پیش از خرید دوباره بررسی کنید");
    await expect(redirectDialog).toContainText(
      /alibaba\.ir|snapptrip\.com|booking\.ir|mrbilit\.com|flytoday(?:ir)?\.com/,
    );
    const redirectBounds = await redirectDialog.boundingBox();
    expect(redirectBounds).not.toBeNull();
    expect(redirectBounds!.x).toBeGreaterThanOrEqual(0);
    expect(redirectBounds!.x + redirectBounds!.width).toBeLessThanOrEqual(width);
    await redirectDialog.getByRole("button", { name: "انصراف" }).click();
  }
});

test("train mobile: full form flow keeps compartment, adult-only passengers, and filters usable", async ({ page }) => {
  const departureDate = await findLiveTrainDate(page);
  test.skip(departureDate === null, "No live Tehran–Qom train inventory was available in the next five days.");
  if (departureDate === null) return;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=train");

  await expect(page.getByRole("checkbox", { name: "کوپه دربست" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "تعداد مسافر، فقط بزرگسال" })).toBeVisible();
  await selectCity(page, "مبدا", "ته", "تهران");
  await selectCity(page, "مقصد", "قم", "قم");
  await chooseDepartureDate(page, departureDate);
  await page.getByRole("button", { name: "جستجو", exact: true }).click();
  await page.waitForURL(/\/results\?/);

  const offersArea = page.locator(".offers-area");
  await expect(offersArea).toHaveAttribute("aria-busy", "false", { timeout: 90_000 });
  await expect(page.getByRole("heading", { name: /گزینه قطار/ })).toBeVisible();
  await expect(page.locator("article.offer-card").first()).toBeVisible();

  const filterToggle = page.getByRole("button", { name: /فیلترها/ });
  await expect(filterToggle).toBeVisible();
  await filterToggle.click();
  await expect(page.getByRole("complementary")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});
