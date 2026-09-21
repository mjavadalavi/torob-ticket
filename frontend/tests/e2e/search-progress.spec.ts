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

const cases = [
  { mode: "flight", label: "پروازها", digit: "1" },
  { mode: "train", label: "قطارها", digit: "2" },
  { mode: "bus", label: "اتوبوس‌ها", digit: "3" },
] as const;

test("queued and running searches use the same stable progress panel", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const searchId = `src_${"8".repeat(32)}`;
  let canRun = false;

  await page.route(`**/api/travel/search-jobs/${searchId}`, async (route) => {
    await route.fulfill({
      status: 200,
      headers: { "retry-after": "1" },
      json: {
        search_id: searchId,
        status: canRun ? "running" : "queued",
        result: null,
        error: null,
      },
    });
  });

  const params = new URLSearchParams({
    mode: "flight",
    origin: "تهران",
    destination: "مشهد",
    date: dateInTehran(7),
    passengers: "1",
    adults: "1",
    intent: "best",
    search_id: searchId,
  });
  await page.goto(`/results?${params.toString()}`);

  const loader = page.locator(".search-progress--flight");
  await expect(loader).toHaveAttribute("data-status", "queued");
  await expect(loader).toContainText("در حال بررسی پروازها");
  await expect(loader.locator(".search-progress__route-summary")).toContainText("تهران");
  await expect(loader.locator(".search-progress__route-summary")).toContainText("مشهد");
  await expect(loader.locator(".search-progress__artwork--flight")).toBeVisible();
  await expect(loader.locator(".search-progress__artwork-background")).toHaveAttribute(
    "src",
    "/images/loading/ticket-search-background-v2.png",
  );
  await expect(loader.locator(".search-progress__artwork-magnifier")).toHaveAttribute(
    "src",
    "/images/loading/ticket-search-magnifier-v2.png",
  );
  await expect(loader.locator(".search-progress__artwork")).toHaveAttribute("data-artwork-ready", "true");
  const toolbarSearch = page.locator(".results-workspace__search-button");
  await toolbarSearch.hover();
  await expect(toolbarSearch).toHaveCSS("transform", "none");

  for (const width of [320, 360, 390, 414, 760, 761, 800, 900, 901, 935, 1024, 1100, 1280, 1440]) {
    await page.setViewportSize({ width, height: width <= 414 ? 844 : 900 });
    const layout = await page.evaluate(() => {
      const clientWidth = document.documentElement.clientWidth;
      const offenders = Array.from(document.body.querySelectorAll("*"))
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            selector: `${element.tagName.toLowerCase()}.${Array.from(element.classList).join(".")}`,
            left: Math.round(rect.left),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
          };
        })
        .filter((item) => item.left < -1 || item.right > clientWidth + 1)
        .slice(0, 8);
      return { clientWidth, scrollWidth: document.documentElement.scrollWidth, offenders };
    });
    expect(layout.scrollWidth, `viewport ${width}: ${JSON.stringify(layout.offenders)}`).toBeLessThanOrEqual(
      layout.clientWidth,
    );
  }

  canRun = true;
  await expect(loader).toHaveAttribute("data-status", "running", { timeout: 10_000 });
  await expect(loader).toContainText("در حال بررسی پروازها");
  await expect(loader.locator(".search-progress__route-summary")).toBeVisible();
  await expect(loader.locator(".search-progress__artwork--flight")).toBeVisible();
  await expect(loader.locator(".search-progress__artwork-magnifier")).toBeVisible();
  await expect(loader.locator(".search-progress__artwork")).toHaveAttribute("data-artwork-ready", "true");
  await expect(loader.locator(".search-progress__skeleton-card")).toHaveCount(2);
  await expect.poll(() => loader.locator(".search-progress__artwork-magnifier").evaluate((element) => (
    getComputedStyle(element).animationName
  ))).toBe("search-progress-magnifier-scan");
  await expect.poll(() => loader.locator(".search-progress__artwork-magnifier").evaluate((element) => (
    getComputedStyle(element).animationDirection
  ))).toBe("alternate");
});

test("same-origin search proxy preserves background-job control headers", async ({ request }) => {
  const response = await request.post("/api/travel/search-jobs", {
    data: {
      mode: "flight",
      origin: "تهران",
      destination: "مشهد",
      departure_date: dateInTehran(7),
      return_date: null,
      passengers: { adults: 1, children: 0, infants: 0 },
      preferences: { mode: "flight" },
      intent: "best",
    },
  });

  expect(response.status()).toBe(202);
  const location = new URL(response.headers()["location"], response.url());
  expect(location.origin).toBe(new URL(response.url()).origin);
  expect(location.pathname).toMatch(
    /^\/api\/travel\/search-jobs\/src_[a-f0-9]{32}$/,
  );
  expect(response.headers()["retry-after"]).toBe("1");
});

test("home searches wait for Retry-After before their first status poll", async ({ page }) => {
  const searchId = `src_${"4".repeat(32)}`;
  let acceptedAt = 0;
  let firstPollAt = 0;

  await page.route("**/api/travel/search-jobs", async (route) => {
    acceptedAt = Date.now();
    await route.fulfill({
      status: 202,
      headers: {
        location: `http://backend.test/api/v1/search-jobs/${searchId}`,
        "retry-after": "1",
      },
      json: { search_id: searchId, status: "queued" },
    });
  });
  await page.route(`**/api/travel/search-jobs/${searchId}`, async (route) => {
    firstPollAt ||= Date.now();
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

  await page.goto("/?mode=flight");
  const origin = page.getByRole("combobox", { name: "مبدا" });
  await origin.fill("تهران");
  await page.getByRole("option").filter({ hasText: "تهران" }).first().click();
  const destination = page.getByRole("combobox", { name: "مقصد" });
  await destination.fill("مشهد");
  await page.getByRole("option").filter({ hasText: "مشهد" }).first().click();
  await page.getByRole("button", { name: "جستجو", exact: true }).click();
  await page.waitForURL(/\/results\?/);

  await expect(page.locator(".search-progress--flight")).toBeVisible();
  await expect(page.getByText("برای این تاریخ بلیتی پیدا نشد", { exact: true })).toBeVisible();
  expect(firstPollAt - acceptedAt).toBeGreaterThanOrEqual(900);
});

for (const item of cases) {
  test(`${item.mode}: resumes a search job with its mode-aware loading state`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const searchId = `src_${item.digit.repeat(32)}`;
    let mayComplete = false;

    await page.route(`**/api/travel/search-jobs/${searchId}`, async (route) => {
      await route.fulfill({
        status: 200,
        json: mayComplete
          ? {
              search_id: searchId,
              status: "completed",
              result: {
                search_id: searchId,
                mode: item.mode,
                intent: "best",
                total: 0,
                providers_queried: 1,
                providers_succeeded: 1,
                provider_failures: [],
                offers: [],
              },
              error: null,
            }
          : {
              search_id: searchId,
              status: "running",
              result: null,
              error: null,
            },
      });
    });

    const destination = item.mode === "train" ? "قم" : "مشهد";
    const params = new URLSearchParams({
      mode: item.mode,
      origin: "تهران",
      destination,
      date: dateInTehran(7),
      passengers: "1",
      adults: "1",
      intent: "best",
      search_id: searchId,
    });
    await page.goto(`/results?${params.toString()}`);

    const loader = page.locator(`.search-progress--${item.mode}`);
    await expect(loader).toBeVisible();
    await expect(loader).toHaveAttribute("data-status", "running");
    await expect(loader).toContainText(`در حال بررسی ${item.label}`);
    await expect(loader).toContainText("تهران");
    await expect(loader).toContainText(destination);
    await expect(loader).toContainText("شناسهٔ پیگیری");
    await expect(loader.locator(".search-progress__route-summary")).toBeVisible();
    await expect(loader.locator(`.search-progress__artwork--${item.mode}`)).toBeVisible();
    await expect(loader.locator(".search-progress__artwork-background")).toHaveAttribute(
      "src",
      "/images/loading/ticket-search-background-v2.png",
    );
    await expect(loader.locator(".search-progress__artwork-magnifier")).toHaveAttribute(
      "src",
      "/images/loading/ticket-search-magnifier-v2.png",
    );
    await expect(loader.locator(".search-progress__artwork")).toHaveAttribute("data-artwork-ready", "true");
    await expect(loader.locator(".search-progress__skeleton-card")).toHaveCount(2);
    await expect.poll(() => loader.locator(".search-progress__artwork-magnifier").evaluate((element) => (
      getComputedStyle(element).animationName
    ))).toBe("search-progress-magnifier-scan");
    await expect.poll(() => loader.locator(".search-progress__artwork-magnifier").evaluate((element) => (
      getComputedStyle(element).animationDirection
    ))).toBe("alternate");
    await expect.poll(() => page.evaluate(() => (
      document.documentElement.scrollWidth <= document.documentElement.clientWidth
    ))).toBe(true);

    mayComplete = true;
    await expect(page.getByText("برای این تاریخ بلیتی پیدا نشد", { exact: true })).toBeVisible({ timeout: 10_000 });
    await expect(loader).toBeHidden();
  });
}

test("empty, provider-unavailable, and failed result states stay responsive", async ({ page }) => {
  const searchId = `src_${"9".repeat(32)}`;
  let state: "empty" | "unavailable" | "failed" = "empty";

  await page.route(`**/api/travel/search-jobs/${searchId}`, async (route) => {
    if (state === "failed") {
      await route.fulfill({
        status: 200,
        json: {
          search_id: searchId,
          status: "failed",
          result: null,
          error: { code: "provider_search_failed", message: "دریافت نتیجه از فروشندگان ممکن نشد.", retryable: true },
        },
      });
      return;
    }
    const unavailable = state === "unavailable";
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
          providers_queried: 2,
          providers_succeeded: unavailable ? 0 : 1,
          provider_failures: unavailable
            ? [{ provider: "seller", message: "هیچ فروشنده‌ای پاسخ نداد." }]
            : [{ provider: "seller", message: "دریافت موجودی یک فروشنده ممکن نشد." }],
          offers: [],
        },
        error: null,
      },
    });
  });

  const params = new URLSearchParams({
    mode: "flight",
    origin: "تهران",
    destination: "مشهد",
    date: dateInTehran(7),
    passengers: "1",
    adults: "1",
    intent: "best",
    search_id: searchId,
  });

  for (const expected of [
    { state: "empty" as const, text: "برای این تاریخ بلیتی پیدا نشد" },
    { state: "unavailable" as const, text: "نتیجه‌ای برای مسیر رفت دریافت نشد" },
    { state: "failed" as const, text: "جست‌وجوی زنده انجام نشد" },
  ]) {
    state = expected.state;
    await page.goto(`/results?${params.toString()}`);
    await expect(page.locator(".results-workspace__state")).toContainText(expected.text, { timeout: 15_000 });
    if (expected.state === "empty") {
      await expect(page.getByRole("heading", { name: "هیچ موردی برای پرواز از تهران به مشهد پیدا نشد" })).toBeVisible();
    }
    await expect(page.locator(".live-note")).toHaveCount(0);
    for (const width of [320, 900, 901, 1100, 1440]) {
      await page.setViewportSize({ width, height: width === 320 ? 800 : 900 });
      await expect.poll(() => page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }))).toEqual({ clientWidth: width, scrollWidth: width });
    }
  }
});
