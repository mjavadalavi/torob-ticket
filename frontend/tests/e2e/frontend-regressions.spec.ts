import { expect, Page, test } from "@playwright/test";

type Mode = "flight" | "train" | "bus";

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

function compactPersianDate(value: string) {
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(`${value}T12:00:00Z`));
}

function sellerOffer(id: string, mode: Mode, amount: number) {
  return {
    id,
    provider: id,
    mode,
    seller: {
      id,
      name: id === "alibaba" ? "علی‌بابا" : "اسنپ‌تریپ",
      rating: 4.7,
      review_count: 1200,
      logo_url: null as string | null,
      logo_alt: null,
      logo_fallback: id === "alibaba" ? "علی‌بابا" : "اسنپ‌تریپ",
    },
    price: { amount, currency: "IRT" },
    capabilities: ["refund_rules"],
    last_updated_at: "2026-09-18T10:00:00+03:30",
    cancellation_summary: "طبق قوانین فروشنده",
    refundable: true,
    remaining_seats: 6,
  };
}

function offerGroup({
  id,
  mode,
  operator,
  logoUrl,
  logoAlt,
  date,
  sellers = [sellerOffer("alibaba", mode, 1_600_000)],
}: {
  id: string;
  mode: Mode;
  operator: string;
  logoUrl?: string | null;
  logoAlt?: string | null;
  date: string;
  sellers?: ReturnType<typeof sellerOffer>[];
}) {
  const details = mode === "flight"
    ? {
        mode,
        origin_airport_code: "THR",
        destination_airport_code: "MHD",
        airline: operator,
        flight_number: "B9 991",
        fare_type: "system",
        cabin_class: "economy",
        baggage_allowance_kg: 20,
      }
    : mode === "train"
      ? {
          mode,
          railway_company: operator,
          train_number: "418",
          class_name: "کوپه ۴ تخته",
          compartment_capacity: 4,
          private_compartment_available: true,
          women_only_available: false,
          vehicle_transport_available: false,
        }
      : {
          mode,
          origin_terminal: "پایانه تهران",
          destination_terminal: "پایانه اصفهان",
          company: operator,
          service_number: "42",
          bus_class: "VIP",
          seat_selection_available: true,
          capacity: 25,
          cancellation_policy: "طبق قوانین فروشنده",
        };
  const lowest = Math.min(...sellers.map((seller) => seller.price.amount));

  return {
    id,
    mode,
    passenger_count: 1,
    origin: "تهران",
    destination: mode === "bus" ? "اصفهان" : "مشهد",
    departure_at: `${date}T08:00:00+03:30`,
    arrival_at: `${date}T10:00:00+03:30`,
    duration_minutes: 120,
    attributes: {
      operator,
      operator_code: id,
      operator_logo_url: logoUrl ?? null,
      operator_logo_alt: logoAlt ?? `نشان شرکت ${operator}`,
      operator_logo_fallback: operator,
      service_number: "42",
      vehicle_class: mode === "flight" ? "economy" : "VIP",
      ticket_type: "system",
      stops: 0,
    },
    mode_details: details,
    available_capabilities: ["refund_rules"],
    lowest_price: { amount: lowest, currency: "IRT" },
    seller_count: sellers.length,
    seller_offers: sellers,
    recommended_seller_offer_id: sellers[0].id,
    recommended_price: sellers[0].price,
    recommended_capabilities: sellers[0].capabilities,
    rank: 1,
    score: 0.95,
    recommendation_reasons: ["lowest_price", "direct"],
    recommendation_summary: "قیمت مناسب و سفر مستقیم",
  };
}

function completedJob({
  searchId,
  mode,
  offers = [],
  returnOffers,
}: {
  searchId: string;
  mode: Mode;
  offers?: ReturnType<typeof offerGroup>[];
  returnOffers?: ReturnType<typeof offerGroup>[];
}) {
  return {
    search_id: searchId,
    status: "completed",
    result: {
      search_id: searchId,
      mode,
      intent: "best",
      total: offers.length,
      providers_queried: 2,
      providers_succeeded: 2,
      provider_failures: [],
      offers,
      ...(returnOffers == null ? {} : {
        return_leg: {
          total: returnOffers.length,
          providers_queried: 2,
          providers_succeeded: 2,
          provider_failures: [],
          offers: returnOffers,
        },
      }),
    },
    error: null,
  };
}

async function mockNearbyDates(page: Page) {
  await page.route("**/api/travel/nearby-dates", async (route) => {
    const request = route.request().postDataJSON() as { mode: Mode; origin: string; destination: string; departure_date: string };
    await route.fulfill({
      status: 200,
      json: {
        mode: request.mode,
        origin: request.origin,
        destination: request.destination,
        selected_date: request.departure_date,
        dates: [-2, -1, 0, 1, 2].map((offset) => ({
          date: shiftDate(request.departure_date, offset),
          offset_days: offset,
          status: "available",
          minimum_price: { amount: 1_500_000 + (offset + 2) * 20_000, currency: "IRT" },
          offer_count: 1,
          providers_queried: 2,
          providers_succeeded: 2,
          provider_failures: [],
        })),
      },
    });
  });
}

async function gotoCompletedResults(page: Page, {
  searchId,
  mode,
  origin = "تهران",
  destination = mode === "bus" ? "اصفهان" : "مشهد",
  date = dateInTehran(7),
  returnDate,
  offers = [],
  returnOffers,
}: {
  searchId: string;
  mode: Mode;
  origin?: string;
  destination?: string;
  date?: string;
  returnDate?: string;
  offers?: ReturnType<typeof offerGroup>[];
  returnOffers?: ReturnType<typeof offerGroup>[];
}) {
  await page.route(`**/api/travel/search-jobs/${searchId}`, async (route) => {
    await route.fulfill({ status: 200, json: completedJob({ searchId, mode, offers, returnOffers }) });
  });
  const params = new URLSearchParams({
    mode,
    origin,
    destination,
    date,
    adults: "1",
    passengers: "1",
    intent: "best",
    search_id: searchId,
  });
  if (mode === "flight") {
    params.set("children", "0");
    params.set("infants", "0");
  }
  if (returnDate) params.set("return_date", returnDate);
  await page.goto(`/results?${params.toString()}`);
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false");
}

test("results mode switch creates exactly one fresh search job", async ({ page }) => {
  const initialSearchId = `src_${"1".repeat(32)}`;
  const switchedSearchId = `src_${"2".repeat(32)}`;
  const requests: unknown[] = [];
  await mockNearbyDates(page);
  await page.route("**/api/travel/search-jobs", async (route) => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({
      status: 202,
      headers: { "retry-after": "1" },
      json: { search_id: switchedSearchId, status: "queued" },
    });
  });
  await page.route(`**/api/travel/search-jobs/${switchedSearchId}`, async (route) => {
    await route.fulfill({ status: 200, json: completedJob({ searchId: switchedSearchId, mode: "flight" }) });
  });
  await gotoCompletedResults(page, { searchId: initialSearchId, mode: "bus" });

  await page.getByRole("button", { name: "پرواز", exact: true }).click();
  await expect(page).toHaveURL(/mode=flight/);
  await expect.poll(() => requests.length).toBe(1);
  await expect(page.locator(".offers-area")).toHaveAttribute("aria-busy", "false", { timeout: 10_000 });
  await page.waitForTimeout(1_100);
  expect(requests).toHaveLength(1);
  expect(requests[0]).toMatchObject({ mode: "flight", preferences: { mode: "flight" } });
});

test("IRANYekan is the loaded computed font", async ({ page }) => {
  await page.goto("/?mode=flight");
  const font = await page.evaluate(async () => {
    await document.fonts.ready;
    return {
      family: getComputedStyle(document.body).fontFamily,
      loaded: document.fonts.check("16px iranyekan"),
      status: document.fonts.status,
    };
  });
  expect(font.family.toLowerCase()).toContain("iranyekan");
  expect(font.loaded).toBe(true);
  expect(font.status).toBe("loaded");
});

test("flight and train result cards render verified operator logos", async ({ page }) => {
  const onePixelPng = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  await page.route("**/api/logo?*", async (route) => {
    await route.fulfill({ status: 200, contentType: "image/png", body: onePixelPng });
  });
  await mockNearbyDates(page);

  for (const item of [
    {
      mode: "flight" as const,
      searchId: `src_${"3".repeat(32)}`,
      operator: "ایران ایرتور",
      logoUrl: "https://cdn.alibaba.ir/static/img/airlines/Domestic/B9.png",
    },
    {
      mode: "train" as const,
      searchId: `src_${"4".repeat(32)}`,
      operator: "رجا",
      logoUrl: "https://fs.snapptrip.com/images/train/uploads/raja.png",
    },
  ]) {
    const offer = offerGroup({
      id: `${item.mode}-logo-offer`,
      mode: item.mode,
      operator: item.operator,
      logoUrl: item.logoUrl,
      logoAlt: `نشان شرکت ${item.operator}`,
      date: dateInTehran(7),
    });
    await gotoCompletedResults(page, { searchId: item.searchId, mode: item.mode, offers: [offer] });
    const logo = page.locator(`article.offer-card--${item.mode} .operator-logo img`);
    await expect(logo).toBeVisible();
    await expect(logo).toHaveAttribute("alt", `نشان شرکت ${item.operator}`);
    await expect(logo).toHaveAttribute("src", /\/api\/logo\?url=/);
    await expect.poll(() => logo.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBe(1);
  }
});

test("result cards show the real source-site logos for their seller offers", async ({ page }) => {
  const onePixelPng = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    "base64",
  );
  await page.route("**/api/logo?*", async (route) => {
    await route.fulfill({ status: 200, contentType: "image/png", body: onePixelPng });
  });
  await mockNearbyDates(page);

  const alibaba = sellerOffer("alibaba", "flight", 1_600_000);
  alibaba.seller.logo_url = "https://cdn.alibaba.ir/h2/desktop/assets/images/shawl_logotype-d6b14ca0.svg";
  const snapptrip = sellerOffer("snapptrip", "flight", 1_650_000);
  snapptrip.seller.logo_url = "https://store.snapptrip.com/assets/builds/website/_next/static/media/logo.12xjc4xr19yoa.png";
  const offer = offerGroup({
    id: "provider-logo-offer",
    mode: "flight",
    operator: "ایران ایرتور",
    logoUrl: "https://cdn.alibaba.ir/static/img/airlines/Domestic/B9.png",
    date: dateInTehran(7),
    sellers: [alibaba, snapptrip],
  });
  await gotoCompletedResults(page, {
    searchId: `src_${"d".repeat(32)}`,
    mode: "flight",
    offers: [offer],
  });

  const sources = page.locator("article.offer-card--flight .offer-card__sources");
  await expect(sources).toHaveAttribute("aria-label", "منابع قیمت: علی‌بابا، اسنپ‌تریپ");
  const logos = sources.locator(".offer-card__source-logo img");
  await expect(logos).toHaveCount(2);
  await expect(logos.nth(0)).toHaveAttribute("src", /\/api\/logo\?url=/);
  await expect(logos.nth(1)).toHaveAttribute("src", /\/api\/logo\?url=/);
  await expect.poll(() => logos.nth(0).evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBe(1);
});

test("flight, train, and bus operator logos have a readable fallback", async ({ page }) => {
  await mockNearbyDates(page);

  for (const [index, item] of ([
    { mode: "flight" as const, operator: "ایران ایرتور" },
    { mode: "train" as const, operator: "رجا" },
    { mode: "bus" as const, operator: "همسفر" },
  ]).entries()) {
    const searchId = `src_${["8", "9", "a"][index].repeat(32)}`;
    const offer = offerGroup({
      id: `${item.mode}-fallback-offer`,
      mode: item.mode,
      operator: item.operator,
      logoUrl: null,
      logoAlt: `نشان شرکت ${item.operator}`,
      date: dateInTehran(7),
    });
    await gotoCompletedResults(page, { searchId, mode: item.mode, offers: [offer] });
    const logo = page.locator(`article.offer-card--${item.mode} .operator-logo`);
    await expect(logo).toHaveAttribute("data-logo-status", "fallback");
    await expect(logo.locator("img")).toHaveCount(0);
    await expect(logo.locator("b")).toContainText(item.operator);
  }
});

test("provider placeholder names are never shown as announced or unknown copy", async ({ page }) => {
  const searchId = `src_${"b".repeat(32)}`;
  const offer = offerGroup({
    id: "placeholder-operator-offer",
    mode: "train",
    operator: "نام فارسی اعلام نشده",
    logoUrl: null,
    logoAlt: "نشان شرکت؛ نام فارسی اعلام نشده",
    date: dateInTehran(7),
  });
  await mockNearbyDates(page);
  await gotoCompletedResults(page, { searchId, mode: "train", offers: [offer] });

  const card = page.locator("article.offer-card--train");
  await expect(card).not.toContainText("اعلام نشده");
  await expect(card.locator(".operator > strong")).toHaveText("—");
  await expect(card.locator(".operator-logo b")).toHaveAccessibleName("نشان شرکت — در دسترس نیست");
});

test("one grouped journey renders one card and the combined seller count", async ({ page }) => {
  const searchId = `src_${"5".repeat(32)}`;
  const sellers = [
    sellerOffer("alibaba", "bus", 1_600_000),
    sellerOffer("snapptrip", "bus", 1_650_000),
  ];
  const groupedOffer = offerGroup({
    id: "grouped-bus-journey",
    mode: "bus",
    operator: "همسفر",
    date: dateInTehran(7),
    sellers,
  });
  await mockNearbyDates(page);
  await gotoCompletedResults(page, { searchId, mode: "bus", offers: [groupedOffer] });

  await expect(page.locator("article.offer-card")).toHaveCount(1);
  await expect(page.locator("article.offer-card")).toContainText("کمترین قیمت در ۲ فروشگاه");
  await expect(page.getByRole("heading", { name: /۱ گزینه اتوبوس/ })).toBeVisible();
});

test("selected nearby date uses the loaded result price when its provider status is unavailable", async ({ page }) => {
  const searchId = `src_${"c".repeat(32)}`;
  const selectedDate = dateInTehran(7);
  const offer = offerGroup({
    id: "selected-date-price-offer",
    mode: "flight",
    operator: "ایران ایرتور",
    date: selectedDate,
  });
  await page.route("**/api/travel/nearby-dates", async (route) => {
    await route.fulfill({
      status: 200,
      json: {
        mode: "flight",
        origin: "تهران",
        destination: "مشهد",
        selected_date: selectedDate,
        dates: [-2, -1, 0, 1, 2].map((offset) => ({
          date: shiftDate(selectedDate, offset),
          offset_days: offset,
          status: offset === 0 ? "provider_unavailable" : "available",
          minimum_price: offset === 0
            ? null
            : { amount: 1_700_000 + offset * 20_000, currency: "IRT" },
          offer_count: offset === 0 ? 0 : 1,
          providers_queried: 2,
          providers_succeeded: offset === 0 ? 0 : 2,
          provider_failures: offset === 0
            ? [{ provider: "seller", message: "دریافت قیمت ممکن نشد." }]
            : [],
        })),
      },
    });
  });
  await gotoCompletedResults(page, {
    searchId,
    mode: "flight",
    date: selectedDate,
    offers: [offer],
  });

  const selectedDateCard = page.getByRole("navigation", { name: "انتخاب تاریخ سفر" })
    .locator('[aria-current="date"]');
  await expect(selectedDateCard).toContainText("۱,۶۰۰,۰۰۰ تومان");
  await expect(selectedDateCard).not.toContainText("قیمت در دسترس نیست");
  await expect(selectedDateCard).toHaveClass(/\bis-available\b/);
  await expect(selectedDateCard).not.toHaveClass(/\bis-provider_unavailable\b/);
});

test("passenger picker enforces infant, total, and adult-only mode limits", async ({ page }) => {
  await page.goto("/?mode=flight");
  const trigger = page.getByRole("combobox", { name: "تعداد مسافر" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "انتخاب تعداد مسافر" });
  const removeAdult = dialog.getByRole("button", { name: "کم کردن بزرگسال" });
  const addAdult = dialog.getByRole("button", { name: "اضافه کردن بزرگسال" });
  const addInfant = dialog.getByRole("button", { name: "اضافه کردن نوزاد" });
  await expect(removeAdult).toBeDisabled();
  await addInfant.click();
  await expect(addInfant).toBeDisabled();
  for (let count = 0; count < 7; count += 1) await addAdult.click();
  await expect(trigger).toContainText("۹ مسافر");
  await expect(dialog.getByRole("button", { name: /^اضافه کردن/ })).toHaveCount(3);
  for (const button of await dialog.getByRole("button", { name: /^اضافه کردن/ }).all()) {
    await expect(button).toBeDisabled();
  }

  for (const mode of ["train", "bus"] as const) {
    await page.goto(`/?mode=${mode}`);
    await page.getByRole("combobox", { name: "تعداد مسافر، فقط بزرگسال" }).click();
    const adultOnlyDialog = page.getByRole("dialog", { name: "انتخاب تعداد مسافر" });
    await expect(adultOnlyDialog).toContainText("فقط مسافر بزرگسال قابل انتخاب است");
    await expect(adultOnlyDialog.getByText("کودک", { exact: true })).toHaveCount(0);
    await expect(adultOnlyDialog.getByText("نوزاد", { exact: true })).toHaveCount(0);
    await expect(adultOnlyDialog.getByRole("button", { name: "کم کردن بزرگسال" })).toBeDisabled();
  }
});

test("nearby-date rails exclude past and invalid round-trip boundaries", async ({ page }) => {
  const today = dateInTehran(0);
  const oneWaySearchId = `src_${"6".repeat(32)}`;
  await mockNearbyDates(page);
  await gotoCompletedResults(page, {
    searchId: oneWaySearchId,
    mode: "flight",
    date: today,
  });
  let rail = page.getByRole("navigation", { name: "انتخاب تاریخ سفر" });
  await expect(rail.getByRole("button", { name: "روز قبل" })).toBeDisabled();
  await expect(rail.locator(".results-workspace__date-button")).toHaveCount(3);
  await expect(rail).not.toContainText("گذشته");
  await expect(rail).not.toContainText(compactPersianDate(shiftDate(today, -1)));

  const departureDate = shiftDate(today, 1);
  const returnDate = shiftDate(today, 3);
  const roundTripSearchId = `src_${"7".repeat(32)}`;
  await gotoCompletedResults(page, {
    searchId: roundTripSearchId,
    mode: "flight",
    date: departureDate,
    returnDate,
    returnOffers: [],
  });
  await expect(page.getByRole("heading", { name: "قیمت روزهای قبل و بعدِ رفت" })).toBeVisible();
  rail = page.getByRole("navigation", { name: "انتخاب تاریخ سفر" });
  await expect(rail.locator(".results-workspace__date-button")).toHaveCount(3);
  await expect(rail).not.toContainText(compactPersianDate(returnDate));

  await page.getByRole("tab", { name: /برگشت/ }).click();
  await expect(page.getByRole("heading", { name: "قیمت روزهای قبل و بعدِ برگشت" })).toBeVisible();
  rail = page.getByRole("navigation", { name: "انتخاب تاریخ سفر" });
  await expect(rail.locator(".results-workspace__date-button")).toHaveCount(4);
  await expect(rail).not.toContainText(compactPersianDate(departureDate));
  await expect(rail.getByRole("button", { name: "روز قبل" })).toBeEnabled();
});

test("expired offer recovery preserves the results query and removes only the stale job id", async ({ page }) => {
  const returnTo = "/results?mode=flight&origin=تهران&destination=اهواز&date=2026-09-23&intent=best&search_id=src_1234567890abcdef1234567890abcdef";
  await page.goto(`/offers/not-a-real-offer?return_to=${encodeURIComponent(returnTo)}`);

  const recovery = page.getByRole("link", { name: "جست‌وجوی دوباره" });
  await expect(recovery).not.toHaveAttribute("href", "/");
  const href = await recovery.getAttribute("href");
  const recovered = new URL(href!, "http://torob-ticket.local");
  expect(recovered.pathname).toBe("/results");
  expect(Object.fromEntries(recovered.searchParams)).toEqual({
    mode: "flight",
    origin: "تهران",
    destination: "اهواز",
    date: "2026-09-23",
    intent: "best",
  });
});
