import { expect, Page, test } from "@playwright/test";

const INITIAL_SEARCH_ID = `src_${"a".repeat(32)}`;

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

function busOffer({
  id,
  operator,
  logoUrl,
  logoAlt,
  logoFallback,
  price,
  rank,
}: {
  id: string;
  operator: string;
  logoUrl: string | null;
  logoAlt: string;
  logoFallback: string;
  price: number;
  rank: number;
}) {
  const sellerOfferId = `${id}-seller`;
  return {
    id,
    mode: "bus",
    passenger_count: 1,
    origin: "بم",
    destination: "کرمان",
    departure_at: "2026-09-24T08:00:00+03:30",
    arrival_at: "2026-09-24T11:30:00+03:30",
    duration_minutes: 210,
    attributes: {
      operator,
      operator_code: id,
      operator_logo_url: logoUrl,
      operator_logo_alt: logoAlt,
      operator_logo_fallback: logoFallback,
      service_number: rank === 1 ? "6323" : "5872",
      vehicle_class: "VIP 25 seats",
      ticket_type: "system",
      stops: 0,
    },
    mode_details: {
      mode: "bus",
      origin_terminal: "پایانه بم",
      destination_terminal: "پایانه کرمان",
      company: operator,
      service_number: rank === 1 ? "6323" : "5872",
      bus_class: "VIP 25 seats",
      seat_selection_available: true,
      capacity: 25,
      cancellation_policy: "قابل استرداد طبق قوانین فروشنده",
    },
    available_capabilities: ["refund_rules", "seat_selection"],
    lowest_price: { amount: price, currency: "IRT" },
    seller_count: 1,
    seller_offers: [
      {
        id: sellerOfferId,
        provider: "alibaba",
        mode: "bus",
        seller: {
          id: "alibaba",
          name: "علی‌بابا",
          rating: 4.7,
          review_count: 1800,
          logo_url: "https://cdn.alibaba.ir/__e2e/alibaba.svg",
          logo_alt: "نشان فروشنده علی‌بابا",
          logo_fallback: "علی‌بابا",
        },
        price: { amount: price, currency: "IRT" },
        capabilities: ["refund_rules", "seat_selection"],
        last_updated_at: "2026-09-17T12:00:00+03:30",
        cancellation_summary: "طبق قوانین فروشنده",
        refundable: true,
        remaining_seats: 8,
      },
    ],
    recommended_seller_offer_id: sellerOfferId,
    recommended_price: { amount: price, currency: "IRT" },
    recommended_capabilities: ["refund_rules", "seat_selection"],
    rank,
    score: rank === 1 ? 0.93 : 0.81,
    recommendation_reasons: rank === 1 ? ["lowest_price", "direct"] : ["direct"],
    recommendation_summary: rank === 1 ? "کمترین قیمت نهایی و مسیر مستقیم" : "مسیر مستقیم",
  };
}

const offers = [
  busOffer({
    id: "royal-safar",
    operator: "رویال سفر ایرانیان",
    logoUrl: "https://cdn.alibaba.ir/__e2e/royal-safar.svg",
    logoAlt: "نشان شرکت رویال سفر ایرانیان",
    logoFallback: "رویال سفر",
    price: 1_630_000,
    rank: 1,
  }),
  busOffer({
    id: "hamsafar",
    operator: "همسفر",
    logoUrl: "https://www.payaneha.com/cloob/Images/0d4f6495ad5be9b0c79c96-hamsafarlogo.png",
    logoAlt: "نشان شرکت همسفر",
    logoFallback: "همسفر",
    price: 1_870_000,
    rank: 2,
  }),
];

const flightOffers = [
  {
    id: "flight-iran-air-tour",
    mode: "flight",
    passenger_count: 1,
    origin: "تهران",
    destination: "مشهد",
    departure_at: "2026-09-24T23:55:00+03:30",
    arrival_at: "2026-09-25T01:25:00+03:30",
    duration_minutes: 90,
    attributes: {
      operator: "هواپیمایی بین‌المللی ایران ایرتور",
      operator_code: "IRB",
      operator_logo_url: "https://cdn.alibaba.ir/static/img/airlines/Domestic/B9.png",
      operator_logo_alt: "نشان شرکت هواپیمایی ایران ایرتور",
      operator_logo_fallback: "ایران ایرتور",
      service_number: "4158",
      vehicle_class: "economy",
      ticket_type: "system",
      stops: 0,
    },
    mode_details: {
      mode: "flight",
      origin_airport: "فرودگاه مهرآباد",
      destination_airport: "فرودگاه مشهد",
      airline: "هواپیمایی بین‌المللی ایران ایرتور",
      flight_number: "4158",
      fare_type: "system",
      cabin_class: "economy",
      baggage_allowance_kg: 20,
    },
    available_capabilities: ["refund_rules"],
    lowest_price: { amount: 6_262_620, currency: "IRT" },
    seller_count: 3,
    seller_offers: [
      {
        id: "flight-iran-air-tour-seller",
        provider: "alibaba",
        mode: "flight",
        seller: {
          id: "alibaba",
          name: "علی‌بابا",
          rating: 4.7,
          review_count: 1800,
          logo_url: null,
          logo_alt: "نشان فروشنده علی‌بابا",
          logo_fallback: "علی‌بابا",
        },
        price: { amount: 6_262_620, currency: "IRT" },
        capabilities: ["refund_rules"],
        last_updated_at: "2026-09-17T12:00:00+03:30",
        cancellation_summary: "طبق قوانین فروشنده",
        refundable: true,
        remaining_seats: 6,
      },
    ],
    recommended_seller_offer_id: "flight-iran-air-tour-seller",
    recommended_price: { amount: 6_262_620, currency: "IRT" },
    recommended_capabilities: ["refund_rules"],
    rank: 1,
    score: 0.95,
    recommendation_reasons: ["lowest_price", "direct", "short_duration"],
    recommendation_summary: "قیمت مناسب، مدت سفر کوتاه و مسیر مستقیم",
  },
];

async function installCompletedBusSearch(page: Page, { logoDelayMs = 0 }: { logoDelayMs?: number } = {}) {
  let searchSequence = 0;
  const requests = new Map<string, Record<string, unknown>>();

  await page.route("**/api/travel/nearby-dates", async (route) => {
    const request = route.request().postDataJSON() as { departure_date?: string };
    const selectedDate = request.departure_date ?? dateInTehran(7);
    await route.fulfill({
      status: 200,
      json: {
        mode: "bus",
        origin: "بم",
        destination: "کرمان",
        selected_date: selectedDate,
        dates: [-2, -1, 0, 1, 2].map((offsetDays) => ({
          date: shiftDate(selectedDate, offsetDays),
          offset_days: offsetDays,
          status: "available",
          minimum_price: {
            amount: 1_550_000 + (offsetDays + 2) * 40_000,
            currency: "IRT",
          },
          offer_count: 2,
          providers_queried: 2,
          providers_succeeded: 2,
          provider_failures: [],
        })),
      },
    });
  });

  await page.route("**/api/logo?url=*", async (route) => {
    const requestedLogo = new URL(route.request().url()).searchParams.get("url") ?? "";
    const isSeller = requestedLogo.endsWith("/alibaba.svg");
    if (!isSeller && logoDelayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, logoDelayMs));
    }
    await route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: isSeller
        ? '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#f6a900"/><path fill="#fff" d="M14 20h36v8H14zm8 16h20v8H22z"/></svg>'
        : '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#e51b35"/><path fill="#fff" d="M18 18h28v8H36v20h-8V26H18z"/></svg>',
    });
  });

  await page.route("**/api/travel/search-jobs", async (route) => {
    searchSequence += 1;
    const searchId = `src_${searchSequence.toString(16).padStart(32, "0")}`;
    requests.set(searchId, route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 202,
      headers: { "retry-after": "0" },
      json: { search_id: searchId, status: "queued" },
    });
  });

  await page.route(/\/api\/travel\/search-jobs\/src_[a-f0-9]{32}(?:\?.*)?$/, async (route) => {
    const searchId = route.request().url().match(/src_[a-f0-9]{32}/)?.[0] ?? INITIAL_SEARCH_ID;
    const request = requests.get(searchId);
    const intent = typeof request?.intent === "string" ? request.intent : "best";
    await route.fulfill({
      status: 200,
      json: {
        search_id: searchId,
        status: "completed",
        result: {
          search_id: searchId,
          mode: "bus",
          intent,
          total: offers.length,
          providers_queried: 2,
          providers_succeeded: 2,
          provider_failures: [],
          offers,
        },
        error: null,
      },
    });
  });
}

async function gotoBusResults(page: Page, width = 390) {
  await page.setViewportSize({ width, height: width === 320 ? 800 : 844 });
  const params = new URLSearchParams({
    mode: "bus",
    origin: "بم",
    destination: "کرمان",
    date: dateInTehran(7),
    passengers: "1",
    adults: "1",
    intent: "best",
    search_id: INITIAL_SEARCH_ID,
  });
  await page.goto(`/results?${params.toString()}`);
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("article.offer-card")).toHaveCount(offers.length);
}

async function installCompletedFlightSearch(page: Page) {
  await page.route("**/api/travel/nearby-dates", async (route) => {
    const request = route.request().postDataJSON() as { departure_date?: string };
    const selectedDate = request.departure_date ?? dateInTehran(7);
    await route.fulfill({
      status: 200,
      json: {
        mode: "flight",
        origin: "تهران",
        destination: "مشهد",
        selected_date: selectedDate,
        dates: [-2, -1, 0, 1, 2].map((offsetDays) => ({
          date: shiftDate(selectedDate, offsetDays),
          offset_days: offsetDays,
          status: "available",
          minimum_price: { amount: 6_000_000, currency: "IRT" },
          offer_count: 1,
          providers_queried: 3,
          providers_succeeded: 3,
          provider_failures: [],
        })),
      },
    });
  });
  await page.route(/\/api\/travel\/search-jobs\/src_[a-f0-9]{32}(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      json: {
        search_id: INITIAL_SEARCH_ID,
        status: "completed",
        result: {
          search_id: INITIAL_SEARCH_ID,
          mode: "flight",
          intent: "best",
          total: flightOffers.length,
          providers_queried: 3,
          providers_succeeded: 3,
          provider_failures: [],
          offers: flightOffers,
        },
        error: null,
      },
    });
  });
}

async function gotoFlightResults(page: Page, width: number) {
  await page.setViewportSize({ width, height: width <= 492 ? 844 : 900 });
  const params = new URLSearchParams({
    mode: "flight",
    origin: "تهران",
    destination: "مشهد",
    date: dateInTehran(7),
    passengers: "1",
    adults: "1",
    children: "0",
    infants: "0",
    intent: "best",
    search_id: INITIAL_SEARCH_ID,
  });
  await page.goto(`/results?${params.toString()}`);
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("article.offer-card--flight")).toHaveCount(1);
}

test("completed bus results stay responsive and keep the icon centered on its dotted track", async ({ page }) => {
  await installCompletedBusSearch(page);
  for (const width of [320, 360, 390, 414, 760, 761, 800, 900, 901, 935, 1024, 1100, 1280, 1440]) {
    await gotoBusResults(page, width);
    await expect.poll(() => page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))).toEqual({ clientWidth: width, scrollWidth: width });
    await expectInsideViewport(page, ".results-workspace__toolbar");
    await expectInsideViewport(page, ".offers-area");
    await expectInsideViewport(page, "article.offer-card:first-of-type");
    const card = page.locator("article.offer-card--bus").first();
    await expect(card.locator(".journey-mode img")).toHaveAttribute(
      "src",
      "/images/icons/mode-bus-v2.png",
    );
    const trackGeometry = await card.locator(".journey-line__track").evaluate((track) => {
      const trackRect = track.getBoundingClientRect();
      const iconRect = track.querySelector(".journey-mode")?.getBoundingClientRect();
      const lineTop = Number.parseFloat(getComputedStyle(track, "::before").top);
      return {
        trackCenter: trackRect.top + trackRect.height / 2,
        iconCenter: iconRect ? iconRect.top + iconRect.height / 2 : null,
        lineTop,
        expectedLineTop: trackRect.height / 2,
      };
    });
    expect(trackGeometry.iconCenter).not.toBeNull();
    expect(Math.abs(trackGeometry.iconCenter! - trackGeometry.trackCenter)).toBeLessThanOrEqual(1);
    expect(Math.abs(trackGeometry.lineTop - trackGeometry.expectedLineTop)).toBeLessThanOrEqual(1);
  }
});

test("flight card keeps its operator, route, explanation, and price inside narrow desktop columns", async ({ page }) => {
  await installCompletedFlightSearch(page);
  for (const width of [360, 492, 760, 901, 1024, 1100, 1280, 1440]) {
    await gotoFlightResults(page, width);
    await expect.poll(() => page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))).toEqual({ clientWidth: width, scrollWidth: width });

    const card = page.locator("article.offer-card--flight");
    await expect(card.locator(".journey-mode img")).toHaveAttribute(
      "src",
      "/images/icons/mode-flight-v2.png",
    );
    await expect(card.locator(".operator")).toContainText("ایران ایرتور");
    await expect(card.locator(".journey")).toContainText("تهران");
    await expect(card.locator(".journey")).toContainText("مشهد");
    await expect(card.locator(".why")).toBeVisible();
    await expect(card.locator(".why")).toContainText("رتبه‌بندی بر اساس");
    await expect(card.locator(".why")).not.toContainText("پیشنهاد");
    await expect(card.locator(".price-box")).toContainText("۶,۲۶۲,۶۲۰");
    await expect(card.getByRole("link", { name: "مقایسه فروشنده‌ها" })).toBeVisible();
    await expect(page.locator(".results-workspace__desktop-sort")).toHaveCount(0);
    expect(await card.evaluate((element) => {
      const cardBounds = element.getBoundingClientRect();
      return [".operator", ".journey", ".why", ".price-box"].every((selector) => {
        const bounds = element.querySelector(selector)?.getBoundingClientRect();
        return bounds
          && bounds.left >= cardBounds.left - 1
          && bounds.right <= cardBounds.right + 1;
      });
    })).toBe(true);
  }
});

test("mobile city picker keeps the search input visible and filters the city list", async ({ page }) => {
  await page.route("**/api/locations?*", async (route) => {
    const query = new URL(route.request().url()).searchParams.get("q") ?? "";
    await route.fulfill({
      status: 200,
      json: {
        mode: "train",
        query,
        total: query ? 1 : 2,
        providers_queried: 3,
        providers_succeeded: 3,
        provider_failures: [],
        locations: query
          ? [{ code: "THR", name: "تهران", mode: "train", kind: "railway_station", popular: true, providers: ["alibaba"] }]
          : [
              { code: "THR", name: "تهران", mode: "train", kind: "railway_station", popular: true, providers: ["alibaba"] },
              { code: "MHD", name: "مشهد", mode: "train", kind: "railway_station", popular: true, providers: ["alibaba"] },
            ],
      },
    });
  });
  await page.setViewportSize({ width: 492, height: 759 });
  await page.goto("/?mode=train");

  const origin = page.getByRole("combobox", { name: "مبدا" });
  await origin.click();
  const picker = page.locator(".city-combobox.is-open");
  await expect(picker).toBeVisible();
  await expect(origin).toBeVisible();
  const pickerBounds = await picker.boundingBox();
  expect(pickerBounds?.x).toBe(0);
  expect(pickerBounds?.width).toBe(492);

  await origin.fill("تهران");
  await expect(page.getByRole("option", { name: /تهران/ })).toBeVisible();
  await expect(page.getByRole("option")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "بستن فهرست شهرها" })).toBeVisible();
});

async function expectInsideViewport(page: Page, selector: string) {
  const locator = page.locator(selector);
  await expect(locator).toBeVisible();
  const bounds = await locator.boundingBox();
  expect(bounds, `${selector} must have layout bounds`).not.toBeNull();
  expect(bounds!.x, `${selector} must not overflow the right RTL edge`).toBeGreaterThanOrEqual(0);
  expect(bounds!.x + bounds!.width, `${selector} must not overflow the left RTL edge`).toBeLessThanOrEqual(
    await page.evaluate(() => window.innerWidth),
  );
}

async function expectVerticallySeparated(page: Page, upperSelector: string, lowerSelector: string) {
  const upper = await page.locator(upperSelector).boundingBox();
  const lower = await page.locator(lowerSelector).boundingBox();
  expect(upper, `${upperSelector} must have layout bounds`).not.toBeNull();
  expect(lower, `${lowerSelector} must have layout bounds`).not.toBeNull();
  expect(
    upper!.y + upper!.height,
    `${upperSelector} must not overlap ${lowerSelector}`,
  ).toBeLessThanOrEqual(lower!.y);
}

for (const width of [320, 414] as const) {
  test(`mobile results controls remain usable without horizontal overflow at ${width}px`, async ({ page }) => {
    await installCompletedBusSearch(page);
    await page.setViewportSize({ width, height: width === 320 ? 800 : 844 });
    await page.goto("/?mode=bus");

    const profile = page.locator(".site-header .login");
    await expect(profile).toBeVisible();
    await expect(profile).toHaveAccessibleName(/ورود|حساب کاربری/);
    const profileMetrics = await profile.evaluate((element) => {
      const bounds = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      const icon = element.querySelector("svg")?.getBoundingClientRect();
      return {
        width: bounds.width,
        height: bounds.height,
        borderWidth: style.borderTopWidth,
        iconWidth: icon?.width ?? 0,
      };
    });
    expect(profileMetrics.width).toBeGreaterThanOrEqual(44);
    expect(profileMetrics.width).toBeLessThanOrEqual(52);
    expect(profileMetrics.height).toBeGreaterThanOrEqual(44);
    expect(profileMetrics.height).toBeLessThanOrEqual(52);
    expect(profileMetrics.iconWidth).toBeLessThanOrEqual(24);
    expect(profileMetrics.borderWidth).toBe("0px");

    await gotoBusResults(page, width);
    await expect.poll(() => page.evaluate(() => ({
      pageWidth: document.documentElement.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
    }))).toEqual({ pageWidth: width, viewportWidth: width });

    await expectInsideViewport(page, ".offers-title h1");
    await expectInsideViewport(page, ".results-workspace__filter-toggle");
    await expectInsideViewport(page, ".results-workspace__mobile-controls .results-workspace__sort-trigger");
    await expectInsideViewport(page, ".results-workspace__toolbar-date");
    await expectInsideViewport(page, ".results-workspace__search-button");
    await expect(page.locator(".results-workspace__toolbar-date")).toContainText(/تاریخ سفر|رفت/);
    await expectVerticallySeparated(page, ".results-workspace__edit-extras", ".results-workspace__toolbar-date");
    await expectVerticallySeparated(page, ".results-workspace__toolbar-date", ".results-workspace__passenger-field");
    await expectVerticallySeparated(page, ".results-workspace__passenger-field", ".results-workspace__search-button");
    await expect(page.locator(".results-workspace__intent-tabs")).toBeHidden();
    await expect(page.locator(".results-workspace__explanation")).toBeHidden();

    const filterToggle = page.getByRole("button", { name: /فیلترها/ });
    const sortTrigger = page.locator(".results-workspace__mobile-controls .results-workspace__sort-trigger");
    const filterBounds = await filterToggle.boundingBox();
    const sortBounds = await sortTrigger.boundingBox();
    expect(filterBounds!.height).toBeGreaterThanOrEqual(44);
    expect(sortBounds!.height).toBeGreaterThanOrEqual(44);
    expect(Math.abs(filterBounds!.y - sortBounds!.y)).toBeLessThanOrEqual(4);
    expect(filterBounds!.width).toBeLessThan(width * 0.6);
    expect(sortBounds!.width).toBeLessThan(width * 0.6);

    await filterToggle.click();
    const filters = page.locator("#results-filters-panel");
    await expect(filters).toBeVisible();
    const operatorFilter = filters.locator("label.check").filter({ hasText: "رویال سفر ایرانیان" });
    await operatorFilter.click();
    await expect(operatorFilter.locator('input[type="checkbox"]')).toBeChecked();
    await expect(filterToggle).toHaveAccessibleName(/۱ فیلتر فعال/);
    await expect(page.locator("article.offer-card")).toHaveCount(1);
    await filterToggle.click();
    await expect(filters).toBeHidden();

    await sortTrigger.click();
    const sortMenu = page.getByRole("listbox", { name: "روش مرتب‌سازی" });
    await expect(sortMenu).toBeVisible();
    await expectInsideViewport(page, ".results-workspace__sort-menu");
    await sortMenu.getByRole("option", { name: /ارزان‌ترین/ }).click();
    await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");
    await expect(sortTrigger).toContainText("ارزان‌ترین");
    await expect(page).toHaveURL(/intent=cheapest/);
  });
}

test("mobile adjacent-date rail exposes nearby dates and starts a new search", async ({ page }) => {
  await installCompletedBusSearch(page);
  await gotoBusResults(page, 320);

  const rail = page.getByRole("navigation", { name: "انتخاب تاریخ سفر" });
  await expect(rail).toBeVisible();
  const dates = rail.locator(".results-workspace__date-button");
  expect(await dates.count()).toBeGreaterThanOrEqual(5);

  const activeDate = rail.locator('.results-workspace__date-button[aria-current="date"]');
  await expect(activeDate).toHaveCount(1);
  const activeIndex = await dates.evaluateAll((buttons) =>
    buttons.findIndex((button) => button.getAttribute("aria-current") === "date"),
  );
  expect(activeIndex).toBeGreaterThan(0);
  expect(activeIndex).toBeLessThan((await dates.count()) - 1);

  const previousDate = dates.nth(activeIndex - 1);
  const nextDate = dates.nth(activeIndex + 1);
  await expect(previousDate).toContainText("تومان");
  await expect(nextDate).toContainText("تومان");
  await expect(previousDate).not.toContainText("بررسی قیمت");
  await expect(nextDate).not.toContainText("بررسی قیمت");

  const originalDate = new URL(page.url()).searchParams.get("date")!;
  await previousDate.click();
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");
  await expect.poll(() => new URL(page.url()).searchParams.get("date")).toBe(shiftDate(originalDate, -1));
  await expect(rail.locator('.results-workspace__date-button[aria-current="date"]')).toHaveCount(1);
});

test("provider-backed operator logos have meaningful alt text and a verified source", async ({ page }) => {
  await installCompletedBusSearch(page);
  await gotoBusResults(page, 390);

  const royalSafar = page.locator("article.offer-card").filter({ hasText: "رویال سفر ایرانیان" });
  const logo = royalSafar.locator(".operator-logo img");
  await expect(logo).toBeVisible();
  await expect(logo).toHaveAttribute("alt", "نشان شرکت رویال سفر ایرانیان");
  await expect(logo).toHaveAttribute("src", /\/api\/logo\?url=/);
  await expect.poll(() => logo.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);

  const hamsafar = page.locator("article.offer-card").filter({ hasText: "همسفر" });
  const hamsafarLogo = hamsafar.locator(".operator-logo img");
  await expect(hamsafarLogo).toBeVisible();
  await expect(hamsafarLogo).toHaveAttribute("alt", "نشان شرکت همسفر");
  await expect(hamsafarLogo).toHaveAttribute("src", /\/api\/logo\?url=/);
  await expect.poll(() => hamsafarLogo.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
});

test("a stalled provider logo falls back instead of loading forever", async ({ page }) => {
  await installCompletedBusSearch(page, { logoDelayMs: 7_000 });
  await gotoBusResults(page, 390);

  const royalSafar = page.locator("article.offer-card").filter({ hasText: "رویال سفر ایرانیان" });
  const logo = royalSafar.locator(".operator-logo");
  await expect(logo).toHaveAttribute("data-logo-status", "fallback", { timeout: 8_000 });
  await expect(logo.locator("img")).toHaveCount(0);
  await expect(logo.locator("b")).toContainText("رویال سفر");
});
