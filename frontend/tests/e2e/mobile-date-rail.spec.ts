import { expect, test } from "@playwright/test";

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

function shiftIsoDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

test("mobile date rail centers the active date and keeps swipe scrolling", async ({ page }) => {
  const searchIds = [
    `src_${"a".repeat(32)}`,
    `src_${"b".repeat(32)}`,
  ];
  let searchCount = 0;

  await page.route("**/api/travel/search-jobs", async (route) => {
    const searchId = searchIds[Math.min(searchCount, searchIds.length - 1)];
    searchCount += 1;
    await route.fulfill({ status: 202, json: { search_id: searchId, status: "queued" } });
  });
  await page.route(/\/api\/travel\/search-jobs\/src_[a-f0-9]{32}$/, async (route) => {
    const searchId = route.request().url().match(/src_[a-f0-9]{32}$/)?.[0] ?? searchIds[0];
    await route.fulfill({
      status: 200,
      json: {
        search_id: searchId,
        status: "completed",
        result: {
          search_id: searchId,
          mode: "flight",
          intent: "best",
          total: 0,
          providers_queried: 1,
          providers_succeeded: 1,
          provider_failures: [],
          offers: [],
        },
        error: null,
      },
    });
  });

  await page.setViewportSize({ width: 320, height: 800 });
  const departureDate = dateInTehran(7);
  await page.route("**/api/travel/nearby-dates", async (route) => {
    const statuses = ["available", "availability_unknown", "sold_out", "provider_unavailable", "available"] as const;
    await route.fulfill({
      status: 200,
      json: {
        mode: "flight",
        origin: "تهران",
        destination: "مشهد",
        selected_date: departureDate,
        dates: statuses.map((status, index) => ({
          date: shiftIsoDate(departureDate, index - 2),
          offset_days: index - 2,
          status,
          minimum_price: status === "available" ? { amount: 4_500_000 + index * 100_000, currency: "IRT" } : null,
          offer_count: status === "available" ? 3 : 0,
          providers_queried: 2,
          providers_succeeded: status === "provider_unavailable" ? 0 : status === "availability_unknown" ? 1 : 2,
          provider_failures: status === "availability_unknown" || status === "provider_unavailable"
            ? [{ provider: "seller", message: "دریافت موجودی یک فروشنده ممکن نشد." }]
            : [],
        })),
      },
    });
  });
  const params = new URLSearchParams({
    mode: "flight",
    origin: "تهران",
    destination: "مشهد",
    date: departureDate,
    passengers: "1",
    adults: "1",
    children: "0",
    infants: "0",
    intent: "best",
  });
  await page.goto(`/results?${params.toString()}`);
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");

  const rail = page.getByRole("navigation", { name: "انتخاب تاریخ سفر" });
  await expect(page.getByRole("heading", { name: "قیمت روزهای قبل و بعد" })).toBeVisible();
  await expect(rail).toContainText("در حال بررسی");
  await expect(rail).toContainText("قیمت در دسترس نیست");
  const activeDate = rail.locator('[aria-current="date"]');
  const centerDelta = () => activeDate.evaluate((element) => {
    const activeRect = element.getBoundingClientRect();
    const railRect = element.parentElement!.getBoundingClientRect();
    return Math.abs(
      activeRect.left + activeRect.width / 2
      - (railRect.left + railRect.width / 2),
    );
  });

  await expect.poll(centerDelta).toBeLessThan(2);
  const scrollState = await rail.evaluate((element) => ({
    overflowX: getComputedStyle(element).overflowX,
    scrollbarWidth: getComputedStyle(element).getPropertyValue("scrollbar-width"),
    isScrollable: element.scrollWidth > element.clientWidth,
  }));
  expect(scrollState).toEqual({
    overflowX: "auto",
    scrollbarWidth: "none",
    isScrollable: true,
  });

  const previousLabel = await activeDate.innerText();
  await rail.evaluate((element) => { element.scrollLeft = 0; });
  await rail.locator(".results-workspace__date-button").nth(1).click();
  await expect.poll(() => activeDate.innerText()).not.toBe(previousLabel);
  await expect.poll(centerDelta).toBeLessThan(2);
});
