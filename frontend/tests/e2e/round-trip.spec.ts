import { expect, Page, test } from "@playwright/test";

type SearchRequestBody = {
  mode: "bus";
  origin: string;
  destination: string;
  departure_date: string;
  return_date: string | null;
  intent: "best" | "cheapest" | "fastest";
};

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

function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function persianPart(value: string, type: "day" | "month" | "year") {
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    timeZone: "UTC",
    [type]: "numeric",
  }).format(new Date(`${value}T00:00:00Z`));
}

function offer({
  id,
  origin,
  destination,
  date,
  operator,
}: {
  id: string;
  origin: string;
  destination: string;
  date: string;
  operator: string;
}) {
  const sellerOfferId = `${id}-seller`;
  return {
    id,
    mode: "bus",
    passenger_count: 1,
    origin,
    destination,
    departure_at: `${date}T08:00:00+03:30`,
    arrival_at: `${date}T11:30:00+03:30`,
    duration_minutes: 210,
    attributes: {
      operator,
      operator_code: id,
      operator_logo_url: null,
      operator_logo_alt: `نشان ${operator}`,
      operator_logo_fallback: operator,
      service_number: "۴۲",
      vehicle_class: "VIP",
      ticket_type: "system",
      stops: 0,
    },
    mode_details: {
      mode: "bus",
      origin_terminal: `پایانه ${origin}`,
      destination_terminal: `پایانه ${destination}`,
      company: operator,
      service_number: "۴۲",
      bus_class: "VIP",
      seat_selection_available: true,
      capacity: 25,
      cancellation_policy: "طبق قوانین فروشنده",
    },
    available_capabilities: ["refund_rules", "seat_selection"],
    lowest_price: { amount: 1_650_000, currency: "IRT" },
    seller_count: 1,
    seller_offers: [{
      id: sellerOfferId,
      provider: "alibaba",
      mode: "bus",
      seller: {
        id: "alibaba",
        name: "علی‌بابا",
        rating: 4.7,
        review_count: 1800,
        logo_url: null,
        logo_alt: "نشان علی‌بابا",
        logo_fallback: "علی‌بابا",
      },
      price: { amount: 1_650_000, currency: "IRT" },
      capabilities: ["refund_rules", "seat_selection"],
      last_updated_at: "2026-09-17T12:00:00+03:30",
      cancellation_summary: "طبق قوانین فروشنده",
      refundable: true,
      remaining_seats: 7,
    }],
    recommended_seller_offer_id: sellerOfferId,
    recommended_price: { amount: 1_650_000, currency: "IRT" },
    recommended_capabilities: ["refund_rules", "seat_selection"],
    rank: 1,
    score: 0.92,
    recommendation_reasons: ["lowest_price", "direct"],
    recommendation_summary: "کمترین قیمت و مسیر مستقیم",
  };
}

async function installTravelMocks(page: Page) {
  let sequence = 0;
  const requests = new Map<string, SearchRequestBody>();

  await page.route("**/api/locations?*", async (route) => {
    const mode = new URL(route.request().url()).searchParams.get("mode") ?? "bus";
    await route.fulfill({
      status: 200,
      json: {
        mode,
        query: "",
        total: 2,
        providers_queried: 1,
        providers_succeeded: 1,
        provider_failures: [],
        locations: [
          { code: "THR", name: "تهران", mode, kind: "bus_station", popular: true, providers: ["alibaba"] },
          { code: "IFN", name: "اصفهان", mode, kind: "bus_station", popular: true, providers: ["alibaba"] },
        ],
      },
    });
  });

  await page.route("**/api/travel/nearby-dates", async (route) => {
    const request = route.request().postDataJSON() as SearchRequestBody;
    await route.fulfill({
      status: 200,
      json: {
        mode: "bus",
        origin: request.origin,
        destination: request.destination,
        selected_date: request.departure_date,
        dates: [-2, -1, 0, 1, 2].map((offset) => ({
          date: shiftDate(request.departure_date, offset),
          offset_days: offset,
          status: "available",
          minimum_price: { amount: 1_600_000 + (offset + 2) * 25_000, currency: "IRT" },
          offer_count: 1,
          providers_queried: 1,
          providers_succeeded: 1,
          provider_failures: [],
        })),
      },
    });
  });

  await page.route("**/api/travel/search-jobs", async (route) => {
    sequence += 1;
    const searchId = `src_${sequence.toString(16).padStart(32, "0")}`;
    requests.set(searchId, route.request().postDataJSON() as SearchRequestBody);
    await route.fulfill({
      status: 202,
      headers: { "retry-after": "0" },
      json: { search_id: searchId, status: "queued" },
    });
  });

  await page.route(/\/api\/travel\/search-jobs\/src_[a-f0-9]{32}(?:\?.*)?$/, async (route) => {
    const searchId = route.request().url().match(/src_[a-f0-9]{32}/)?.[0] ?? "";
    const request = requests.get(searchId);
    if (!request) {
      await route.fulfill({ status: 404, json: { detail: "جست‌وجو پیدا نشد." } });
      return;
    }
    const outboundOffer = offer({
      id: `${searchId}-outbound`,
      origin: request.origin,
      destination: request.destination,
      date: request.departure_date,
      operator: "همسفر رفت",
    });
    const returnOffer = request.return_date
      ? offer({
          id: `${searchId}-return`,
          origin: request.destination,
          destination: request.origin,
          date: request.return_date,
          operator: "همسفر برگشت",
        })
      : null;
    await route.fulfill({
      status: 200,
      json: {
        search_id: searchId,
        status: "completed",
        result: {
          search_id: searchId,
          mode: "bus",
          intent: request.intent,
          total: 1,
          providers_queried: 1,
          providers_succeeded: 1,
          provider_failures: [],
          offers: [outboundOffer],
          return_leg: returnOffer ? {
            total: 1,
            providers_queried: 1,
            providers_succeeded: 1,
            provider_failures: [],
            offers: [returnOffer],
          } : null,
        },
        error: null,
      },
    });
  });

  return { requests };
}

async function selectCity(page: Page, label: "مبدا" | "مقصد", value: string) {
  const input = page.getByRole("combobox", { name: label });
  await input.fill(value);
  await page.getByRole("option").filter({ hasText: value }).first().click();
}

async function chooseRange(page: Page, departureDate: string, returnDate: string) {
  await page.getByRole("button", { name: "انتخاب تاریخ رفت و برگشت" }).click();
  const dialog = page.getByRole("dialog", { name: "انتخاب تاریخ" });

  async function chooseDate(value: string) {
    const dateButton = dialog.locator(`button[data-date="${value}"]`);
    for (let monthOffset = 0; monthOffset < 3 && await dateButton.count() === 0; monthOffset += 1) {
      await dialog.getByRole("button", { name: "ماه بعد" }).click();
    }
    await expect(dateButton).toBeEnabled();
    await dateButton.click();
  }

  await chooseDate(departureDate);
  await chooseDate(returnDate);
  await expect(dialog).toBeHidden();
}

test("round trip uses one job, preserves the range, and shows independent result legs", async ({ page }) => {
  const { requests } = await installTravelMocks(page);
  const departureDate = dateInTehran(7);
  const returnDate = shiftDate(departureDate, 2);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?mode=bus");

  await selectCity(page, "مبدا", "تهران");
  await selectCity(page, "مقصد", "اصفهان");
  await page.getByRole("button", { name: "رفت‌وبرگشت", exact: true }).click();
  await chooseRange(page, departureDate, returnDate);

  for (const width of [320, 360, 390, 414, 760, 761, 800, 900, 901, 935, 1024, 1100, 1280, 1440]) {
    await page.setViewportSize({ width, height: width <= 414 ? 844 : 900 });
    await expect.poll(() => page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      page: document.documentElement.scrollWidth,
    }))).toEqual({ viewport: width, page: width });
  }

  await page.getByRole("button", { name: "جستجو", exact: true }).click();
  await page.waitForURL(/\/results\?/);
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");

  const url = new URL(page.url());
  expect(url.searchParams.get("date")).toBe(departureDate);
  expect(url.searchParams.get("return_date")).toBe(returnDate);
  expect(requests.size).toBe(1);
  expect([...requests.values()][0]).toMatchObject({
    origin: "تهران",
    destination: "اصفهان",
    departure_date: departureDate,
    return_date: returnDate,
  });

  const legTabs = page.getByRole("tablist", { name: "مسیرهای رفت و برگشت" });
  await expect(legTabs).toBeVisible();
  await expect(page.locator("article.offer-card")).toContainText("همسفر رفت");
  await legTabs.getByRole("tab", { name: /برگشت/ }).click();
  await expect(page.getByRole("heading", { name: /اصفهان به تهران/ })).toBeVisible();
  await expect(page.locator("article.offer-card")).toContainText("همسفر برگشت");
  await expect(page.getByRole("heading", { name: "قیمت روزهای قبل و بعدِ برگشت" })).toBeVisible();

  const toolbar = page.getByRole("form", { name: "جزئیات جست‌وجو" });
  await expect(toolbar.getByRole("button", { name: "انتخاب تاریخ رفت و برگشت" })).toContainText("برگشت");
  const previousSearchId = new URL(page.url()).searchParams.get("search_id");
  await toolbar.getByRole("button", { name: "جستجو", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("search_id")).not.toBe(previousSearchId);
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");
  expect(requests.size).toBe(2);
  expect([...requests.values()][1].return_date).toBe(returnDate);

  for (const width of [320, 360, 390, 414, 760, 761, 800, 900, 901, 935, 1024, 1100, 1280, 1440]) {
    await page.setViewportSize({ width, height: width <= 414 ? 844 : 900 });
    await expect.poll(() => page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      page: document.documentElement.scrollWidth,
    }))).toEqual({ viewport: width, page: width });
  }
});

test("one-way search remains compatible and does not render return-leg controls", async ({ page }) => {
  const { requests } = await installTravelMocks(page);
  await page.goto("/?mode=bus");
  await selectCity(page, "مبدا", "تهران");
  await selectCity(page, "مقصد", "اصفهان");
  await page.getByRole("button", { name: "جستجو", exact: true }).click();
  await page.waitForURL(/\/results\?/);
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");

  expect([...requests.values()][0].return_date).toBeNull();
  expect(new URL(page.url()).searchParams.has("return_date")).toBe(false);
  await expect(page.getByRole("tablist", { name: "مسیرهای رفت و برگشت" })).toHaveCount(0);
  await expect(page.locator("article.offer-card")).toContainText("همسفر رفت");
});
