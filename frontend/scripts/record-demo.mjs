import { execFile } from "node:child_process";
import { mkdtemp, rm, copyFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";

import { chromium, request as playwrightRequest } from "playwright";

const execFileAsync = promisify(execFile);
const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, "../..");
const baseURL = (
  process.env.DEMO_BASE_URL
  ?? process.env.E2E_BASE_URL
  ?? "http://127.0.0.1:3000"
).replace(/\/$/, "");
const outputPath = process.env.DEMO_OUTPUT
  ? path.resolve(process.cwd(), process.env.DEMO_OUTPUT)
  : path.join(repositoryRoot, "demo.mp4");
const maxDurationSeconds = Number(process.env.DEMO_MAX_DURATION_SECONDS ?? "300");
const actionPauseScale = Number(process.env.DEMO_PAUSE_SCALE ?? "1");

const modes = [
  { mode: "flight", label: "پرواز", origin: "تهران", destination: "مشهد" },
  { mode: "train", label: "قطار", origin: "تهران", destination: "مشهد" },
  // This deliberately uses the non-default route the product review called out.
  { mode: "bus", label: "اتوبوس", origin: "تهران", destination: "اصفهان" },
];

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function pause(milliseconds) {
  await sleep(Math.max(0, Math.round(milliseconds * actionPauseScale)));
}

function dateInTehran(daysFromToday) {
  const value = new Date(Date.now() + daysFromToday * 86_400_000);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const part = (type) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function persianDateParts(value) {
  const parts = new Intl.DateTimeFormat("en-US-u-ca-persian-nu-latn", {
    timeZone: "UTC",
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(new Date(`${value}T00:00:00Z`));
  const part = (type) => Number(parts.find((item) => item.type === type)?.value);
  return { year: part("year"), month: part("month"), day: part("day") };
}

function persianDay(value) {
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    timeZone: "UTC",
    day: "numeric",
  }).format(new Date(`${value}T00:00:00Z`));
}

function probePayload(spec, departureDate) {
  return {
    mode: spec.mode,
    origin: spec.origin,
    destination: spec.destination,
    departure_date: departureDate,
    return_date: null,
    passengers: { adults: 1, children: 0, infants: 0 },
    preferences: {
      mode: spec.mode,
      ...(spec.mode === "train"
        ? {
            exclusive_compartment: false,
            passenger_type: "family",
            vehicle_transport: false,
          }
        : {}),
    },
    intent: "best",
  };
}

async function findLiveDate(api, spec, maximumAttempts = 28) {
  const preferredOffsets = [
    7,
    ...Array.from({ length: 28 }, (_, index) => index + 1).filter(
      (offset) => offset !== 7,
    ),
  ];
  const attempts = [];

  for (const offset of preferredOffsets.slice(0, maximumAttempts)) {
    const departureDate = dateInTehran(offset);
    try {
      const response = await api.post("/api/travel/search", {
        data: probePayload(spec, departureDate),
        timeout: 30_000,
      });
      const body = await response.json().catch(() => null);
      attempts.push(`${departureDate}:${response.status()}:${body?.total ?? "?"}`);
      if (
        response.ok()
        && body
        && Number(body.providers_succeeded) > 0
        && Number(body.total) > 0
        && Array.isArray(body.offers)
        && body.offers.length > 0
      ) {
        console.log(
          `[probe] ${spec.mode}: ${departureDate}, ${body.total} result(s), `
          + `${body.providers_succeeded}/${body.providers_queried} provider(s)`,
        );
        return departureDate;
      }
    } catch (error) {
      attempts.push(`${departureDate}:request-error`);
      console.warn(`[probe] ${spec.mode} ${departureDate}: ${error.message}`);
    }
  }

  throw new Error(
    `No live ${spec.mode} inventory was found for ${spec.origin}–${spec.destination}. `
    + `Attempts: ${attempts.join(", ")}`,
  );
}

async function selectCity(page, label, query, city) {
  const input = page.getByRole("combobox", { name: label });
  await input.click();
  await pause(350);
  await input.fill(query);
  const option = page.getByRole("option").filter({ hasText: city }).first();
  await option.waitFor({ state: "visible", timeout: 15_000 });
  await pause(500);
  await option.click();
  await input.waitFor({ state: "visible" });
  if ((await input.inputValue()) !== city) {
    throw new Error(`City selection failed for ${label}: ${city}.`);
  }
}

async function chooseDepartureDate(page, targetDate) {
  await page.getByRole("button", { name: "انتخاب تاریخ رفت" }).click();
  const dialog = page.getByRole("dialog", { name: "انتخاب تاریخ" });
  await dialog.waitFor({ state: "visible" });
  await pause(900);

  // The shared form opens on today. Keep month navigation aligned with the
  // actual calendar default rather than the probe's preferred live date.
  const visibleMonth = persianDateParts(dateInTehran(0));
  const targetMonth = persianDateParts(targetDate);
  const monthDelta = (
    targetMonth.year * 12 + targetMonth.month
    - (visibleMonth.year * 12 + visibleMonth.month)
  );
  const direction = monthDelta > 0 ? "ماه بعد" : "ماه قبل";
  for (let index = 0; index < Math.abs(monthDelta); index += 1) {
    await dialog.getByRole("button", { name: direction }).click();
    await pause(350);
  }

  const dayButton = dialog.getByRole("button", {
    name: persianDay(targetDate),
    exact: true,
  });
  await dayButton.waitFor({ state: "visible" });
  if (await dayButton.isDisabled()) {
    throw new Error(`The probed departure date ${targetDate} is disabled in the UI.`);
  }
  await pause(500);
  await dayButton.click();
  await dialog.waitFor({ state: "hidden" });
}

async function ensureNextJobShowsRunning(page, retryAfterSeconds = 2) {
  const pattern = "**/api/travel/search-jobs/src_*";
  let runningWasShown = false;
  const handler = async (route) => {
    let response;
    try {
      response = await route.fetch();
    } catch {
      await route.continue().catch(() => undefined);
      return;
    }
    const body = await response.json().catch(() => null);
    const headers = response.headers();

    if (body?.status === "running") {
      runningWasShown = true;
      await route.fulfill({
        response,
        headers: { ...headers, "retry-after": String(retryAfterSeconds) },
      });
      return;
    }
    if (body?.status === "completed" && !runningWasShown) {
      runningWasShown = true;
      await route.fulfill({
        status: response.status(),
        headers: {
          "content-type": "application/json; charset=utf-8",
          "retry-after": String(retryAfterSeconds),
        },
        json: { ...body, status: "running", result: null, error: null },
      });
      return;
    }
    await route.fulfill({ response });
  };
  await page.route(pattern, handler);
  return async () => page.unroute(pattern, handler);
}

async function assertNoPlaceholderSeller(page) {
  const bodyText = await page.locator("body").innerText();
  if (/example\.com|starcom|compare five|bad compare/i.test(bodyText)) {
    throw new Error("The production UI still exposes placeholder seller text.");
  }
  const placeholderLinkCount = await page.locator('a[href*="example.com"]').count();
  if (placeholderLinkCount > 0) {
    throw new Error("The production UI still exposes an example.com seller link.");
  }
}

async function waitForNearbyDateStatuses(page) {
  const rail = page.getByRole("navigation", { name: "انتخاب تاریخ سفر" });
  await rail.waitFor({ state: "visible", timeout: 30_000 });
  await page.waitForFunction(() => {
    const labels = Array.from(
      document.querySelectorAll(".results-workspace__date-button b"),
      (node) => node.textContent?.trim() ?? "",
    );
    return labels.length >= 5
      && labels.filter((label) => /تومان|تکمیل ظرفیت|نامشخص|موجود/.test(label)).length >= 3;
  }, undefined, { timeout: 45_000 }).catch(() => {
    console.warn("[record] nearby-date providers did not resolve at least three dates");
  });
  await rail.scrollIntoViewIfNeeded();
  await pause(1_600);
}

async function waitForProviderIdentity(page) {
  const firstOffer = page.locator("article.offer-card").first();
  await firstOffer.waitFor({ state: "visible", timeout: 30_000 });
  await firstOffer.scrollIntoViewIfNeeded();
  const mark = firstOffer.locator(".operator-logo");
  await mark.waitFor({ state: "visible" });
  const image = mark.locator("img");
  if (await image.count()) {
    await page.waitForFunction(
      (selector) => {
        const element = document.querySelector(selector);
        return element instanceof HTMLImageElement && element.complete && element.naturalWidth > 0;
      },
      "article.offer-card .operator-logo img",
      { timeout: 15_000 },
    ).catch(() => console.warn("[record] first operator logo used its Persian fallback"));
  }
  await pause(1_300);
  return firstOffer;
}

async function waitForCompletedResults(page, mode, removeDelay) {
  const offersArea = page.locator(".offers-area");
  let removeActiveDelay = removeDelay;

  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const loader = page.locator(`.search-progress--${mode}`);
    await loader.waitFor({ state: "visible", timeout: 15_000 });
    await pause(1_600);
    await page.waitForFunction(
      () => document.querySelector(".offers-area")?.getAttribute("aria-busy") === "false",
      undefined,
      { timeout: 90_000 },
    );
    await removeActiveDelay();

    const firstOffer = offersArea.locator("article.offer-card").first();
    if (await firstOffer.isVisible()) {
      await pause(1_700);
      return firstOffer;
    }

    const retry = offersArea.getByRole("button", {
      name: "تلاش دوباره",
      exact: true,
    });
    if (attempt < 3 && await retry.isVisible()) {
      console.warn(`[record] ${mode} live job failed; retrying through the UI`);
      removeActiveDelay = await ensureNextJobShowsRunning(page);
      await retry.click();
      continue;
    }

    const text = await offersArea.innerText();
    throw new Error(`Live ${mode} flow returned no visible offer. UI said: ${text}`);
  }

  throw new Error(`Live ${mode} flow exhausted its retry budget.`);
}

async function submitFromHome(page, spec, departureDate) {
  await page.goto(`/?mode=${spec.mode}`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "بلیت ترب" }).waitFor({ state: "visible" });
  await pause(1_300);

  await selectCity(page, "مبدا", spec.origin.slice(0, 2), spec.origin);
  await selectCity(
    page,
    "مقصد",
    spec.destination.slice(0, 2),
    spec.destination,
  );
  await chooseDepartureDate(page, departureDate);

  const removeDelay = await ensureNextJobShowsRunning(page);
  await page.getByRole("button", { name: "جستجو", exact: true }).click();
  await page.waitForURL(/\/results\?/, { timeout: 30_000 });
  return waitForCompletedResults(page, spec.mode, removeDelay);
}

async function showHomeModeTabs(page) {
  console.log("[record] home ticket tabs and searchable city lists");
  await page.goto("/?mode=flight", { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "بلیت ترب" }).waitFor({ state: "visible" });
  await pause(1_000);

  const modeTabs = page.getByRole("navigation", { name: "نوع بلیت" });
  for (const spec of [modes[1], modes[2], modes[0]]) {
    await modeTabs.getByRole("link", { name: spec.label, exact: true }).click();
    await page.waitForURL(new RegExp(`mode=${spec.mode}`));
    await pause(900);
  }

  const origin = page.getByRole("combobox", { name: "مبدا" });
  await origin.click();
  await page.getByRole("listbox", { name: "انتخاب مبدا" }).waitFor({ state: "visible" });
  await pause(800);
  await origin.fill("ته");
  await page.getByRole("option").filter({ hasText: "تهران" }).first().waitFor({
    state: "visible",
    timeout: 15_000,
  });
  await pause(800);
  await page.keyboard.press("Escape");
}

async function openSellerComparison(page, offerCard) {
  const link = offerCard.getByRole("link", { name: "مقایسه فروشنده‌ها" });
  await link.scrollIntoViewIfNeeded();
  await Promise.all([
    page.waitForURL(
      (url) => url.pathname.startsWith("/offers/"),
      { timeout: 60_000 },
    ),
    link.click(),
  ]);
  await page.getByRole("heading", { name: "مقایسه فروشنده‌ها" }).waitFor({
    state: "visible",
    timeout: 60_000,
  });
}

async function showFlightFlow(page, spec, departureDate) {
  console.log("[record] flight home → loader → results");
  await submitFromHome(page, spec, departureDate);
  await assertNoPlaceholderSeller(page);
  await waitForNearbyDateStatuses(page);
  await waitForProviderIdentity(page);

  const removeDelay = await ensureNextJobShowsRunning(page);
  await page.locator(".results-workspace__sort-trigger:visible").first().click();
  const sortMenu = page.getByRole("listbox", { name: "روش مرتب‌سازی" });
  await sortMenu.waitFor({ state: "visible" });
  await pause(650);
  await sortMenu.getByRole("option").filter({ hasText: "ارزان‌ترین" }).click();
  await waitForCompletedResults(page, "flight", removeDelay);

  await openSellerComparison(page, page.locator("article.offer-card").first());
  await assertNoPlaceholderSeller(page);
  await pause(1_300);

  await page.getByRole("button", { name: "جزئیات", exact: true }).first().click();
  const detailsDialog = page.getByRole("dialog", { name: "جزئیات بلیت" });
  await detailsDialog.waitFor({ state: "visible" });
  await page.waitForFunction(
    () => document.querySelector('[role="dialog"][aria-labelledby^="seller-panel-title"]')
      ?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 30_000 },
  );
  await pause(1_500);
  await detailsDialog.getByRole("button", { name: "بستن پنجره" }).click();

  await page.getByRole("button", { name: "قوانین استرداد", exact: true }).first().click();
  const refundDialog = page.getByRole("dialog", { name: "قوانین استرداد" });
  await refundDialog.waitFor({ state: "visible" });
  await page.waitForFunction(
    () => document.querySelector('[role="dialog"][aria-labelledby^="seller-panel-title"]')
      ?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 30_000 },
  );
  await pause(1_500);
  await refundDialog.getByRole("button", { name: "بستن پنجره" }).click();

  await page.getByRole("button", { name: "مشاهده در فروشگاه" }).first().click();
  const redirectDialog = page.getByRole("dialog", { name: "بررسی در سایت فروشنده" });
  await redirectDialog.waitFor({ state: "visible" });
  await page.waitForFunction(
    () => document.querySelector('.seller-redirect-panel[aria-busy="false"]') !== null,
    undefined,
    { timeout: 30_000 },
  );
  await redirectDialog
    .getByText("قیمت، موجودی و جزئیات بلیت را پیش از خرید دوباره بررسی کنید", {
      exact: false,
    })
    .waitFor({ state: "visible" });
  await pause(1_700);
  await redirectDialog.getByRole("button", { name: "انصراف" }).click();
  await pause(600);
}

async function showTrainFlow(page, spec, departureDate) {
  console.log("[record] train home → train-specific loader → live results");
  await submitFromHome(page, spec, departureDate);
  await assertNoPlaceholderSeller(page);
  await waitForNearbyDateStatuses(page);
  await waitForProviderIdentity(page);
}

async function showBusFlow(page, spec, departureDate) {
  console.log("[record] bus home → loader → results → seat map");
  await submitFromHome(page, spec, departureDate);
  const resultsUrl = page.url();
  await assertNoPlaceholderSeller(page);
  await waitForNearbyDateStatuses(page);
  await waitForProviderIdentity(page);

  const seatSelectionCard = page
    .locator("article.offer-card")
    .filter({ hasText: "انتخاب صندلی" })
    .first();
  await seatSelectionCard.waitFor({ state: "visible", timeout: 10_000 });
  await openSellerComparison(page, seatSelectionCard);
  await pause(1_200);

  await page.getByRole("button", { name: "نقشه صندلی", exact: true }).first().click();
  const seatMapDialog = page.getByRole("dialog", { name: "نقشه صندلی" });
  await seatMapDialog.waitFor({ state: "visible" });
  // Seat maps are provider-specific. Some live bus sellers expose the map
  // action but return no seat inventory; keep the recording useful instead of
  // failing the whole demo on that external capability.
  const seat = seatMapDialog.getByRole("listitem").first();
  try {
    await seat.waitFor({ state: "visible", timeout: 10_000 });
    await pause(2_000);
  } catch {
    console.warn("[record] bus provider returned no seat inventory; showing the empty state");
    await pause(1_200);
  }
  await seatMapDialog.getByRole("button", { name: "بستن پنجره" }).click();
  await pause(700);
  return resultsUrl;
}

async function showMobileResults(page, resultsUrl) {
  console.log("[record] mobile results controls, nearby dates, filters, sort, and logos");
  await page.goto(resultsUrl, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(
    () => document.querySelector(".offers-area")?.getAttribute("aria-busy") === "false",
    undefined,
    { timeout: 90_000 },
  );
  await assertNoPlaceholderSeller(page);
  await waitForNearbyDateStatuses(page);

  const controls = page.locator(".results-workspace__mobile-controls");
  await controls.scrollIntoViewIfNeeded();
  await pause(1_700);

  const filterToggle = page.getByRole("button", { name: /فیلترها/ });
  await filterToggle.click();
  const filters = page.locator("#results-filters-panel");
  await filters.waitFor({ state: "visible" });
  await pause(1_200);
  const firstFilter = filters.locator('label.check:has(input[type="checkbox"])').first();
  if (await firstFilter.isVisible()) {
    await firstFilter.click();
    await page.waitForFunction(
      () => /فیلتر فعال/.test(
        document.querySelector(".results-workspace__filter-toggle")?.getAttribute("aria-label")
          ?? document.querySelector(".results-workspace__filter-toggle b")?.getAttribute("aria-label")
          ?? "",
      ),
    ).catch(() => undefined);
    await pause(900);
  }
  await filterToggle.click();
  await filters.waitFor({ state: "hidden" });

  const sortTrigger = page.locator(
    ".results-workspace__mobile-controls .results-workspace__sort-trigger",
  );
  await sortTrigger.click();
  await page.getByRole("listbox", { name: "روش مرتب‌سازی" }).waitFor({ state: "visible" });
  await pause(1_500);
  await sortTrigger.click();

  await waitForProviderIdentity(page);
}

async function transcodeAndVerify(rawVideos, encodedVideo) {
  const inputs = rawVideos.flatMap(({ file }) => ["-i", file]);
  const filters = rawVideos.map(({ kind }, index) => kind === "mobile"
    ? `[${index}:v]scale=-2:900:flags=lanczos,pad=1440:900:(ow-iw)/2:0:color=0xf3f6fb,fps=25,setsar=1,format=yuv420p[v${index}]`
    : `[${index}:v]scale=1440:900:flags=lanczos,fps=25,setsar=1,format=yuv420p[v${index}]`);
  filters.push(
    `${rawVideos.map((_, index) => `[v${index}]`).join("")}concat=n=${rawVideos.length}:v=1:a=0[outv]`,
  );

  await execFileAsync("ffmpeg", [
    "-y",
    ...inputs,
    "-filter_complex",
    filters.join(";"),
    "-map",
    "[outv]",
    "-c:v",
    "libx264",
    "-preset",
    "medium",
    "-crf",
    "20",
    "-pix_fmt",
    "yuv420p",
    "-r",
    "25",
    "-movflags",
    "+faststart",
    "-an",
    encodedVideo,
  ], { maxBuffer: 10 * 1024 * 1024 });

  const { stdout } = await execFileAsync("ffprobe", [
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=codec_name,pix_fmt,width,height:format=duration",
    "-of",
    "json",
    encodedVideo,
  ]);
  const probe = JSON.parse(stdout);
  const stream = probe.streams?.[0];
  const duration = Number(probe.format?.duration);

  if (!stream || stream.codec_name !== "h264" || stream.pix_fmt !== "yuv420p") {
    throw new Error(`Unexpected video encoding: ${JSON.stringify(stream)}`);
  }
  if (stream.width !== 1440 || stream.height !== 900) {
    throw new Error(`Unexpected video dimensions: ${stream.width}x${stream.height}.`);
  }
  if (!Number.isFinite(duration) || duration <= 0 || duration >= maxDurationSeconds) {
    throw new Error(
      `Demo duration must be between 0 and ${maxDurationSeconds} seconds; got ${duration}.`,
    );
  }
  return { duration, stream };
}

async function recordSegment(browser, rawDirectory, options, run) {
  const context = await browser.newContext({
    baseURL,
    viewport: options.viewport,
    locale: "fa-IR",
    timezoneId: "Asia/Tehran",
    colorScheme: "light",
    recordVideo: {
      dir: rawDirectory,
      size: options.viewport,
    },
  });
  const page = await context.newPage();
  const video = page.video();
  page.setDefaultTimeout(30_000);
  page.setDefaultNavigationTimeout(30_000);
  page.on("pageerror", (error) => console.warn(`[pageerror] ${error.message}`));

  try {
    const result = await run(page);
    await context.close();
    if (!video) throw new Error(`Playwright did not start the ${options.kind} recording.`);
    return { file: await video.path(), kind: options.kind, result };
  } catch (error) {
    await context.close().catch(() => undefined);
    throw error;
  }
}

async function main() {
  if (!Number.isFinite(maxDurationSeconds) || maxDurationSeconds <= 0) {
    throw new Error("DEMO_MAX_DURATION_SECONDS must be a positive number.");
  }
  if (!Number.isFinite(actionPauseScale) || actionPauseScale < 0) {
    throw new Error("DEMO_PAUSE_SCALE must be a non-negative number.");
  }

  const workDirectory = await mkdtemp(path.join(tmpdir(), "torob-travel-demo-"));
  const rawDirectory = path.join(workDirectory, "raw");
  const encodedVideo = path.join(workDirectory, "demo.mp4");
  let browser;
  let watchdog;

  try {
    const api = await playwrightRequest.newContext({
      baseURL,
      extraHTTPHeaders: { Accept: "application/json" },
    });
    const home = await api.get("/", { timeout: 15_000 });
    if (!home.ok()) {
      throw new Error(`Frontend at ${baseURL} returned HTTP ${home.status()}.`);
    }

    console.log(`[probe] finding live inventory through ${baseURL}`);
    const liveDates = {
      bus: await findLiveDate(api, modes[2]),
      flight: await findLiveDate(api, modes[0]),
      train: await findLiveDate(api, modes[1]),
    };
    await api.dispose();

    browser = await chromium.launch({
      headless: process.env.DEMO_HEADED !== "1",
    });
    const recordingBudget = Math.max(1, maxDurationSeconds - 15) * 1_000;
    watchdog = setTimeout(() => {
      console.error(`[record] exceeded ${recordingBudget / 1_000}s recording budget`);
      void browser?.close().catch(() => undefined);
    }, recordingBudget);

    const desktop = await recordSegment(
      browser,
      rawDirectory,
      { kind: "desktop", viewport: { width: 1440, height: 900 } },
      async (page) => {
        await showHomeModeTabs(page);
        await showTrainFlow(page, modes[1], liveDates.train);
        await showFlightFlow(page, modes[0], liveDates.flight);
        return showBusFlow(page, modes[2], liveDates.bus);
      },
    );
    const mobile = await recordSegment(
      browser,
      rawDirectory,
      { kind: "mobile", viewport: { width: 390, height: 844 } },
      (page) => showMobileResults(page, desktop.result),
    );

    clearTimeout(watchdog);
    watchdog = undefined;
    await browser.close();
    browser = undefined;

    console.log("[encode] creating H.264 MP4");
    const verification = await transcodeAndVerify([desktop, mobile], encodedVideo);
    await copyFile(encodedVideo, outputPath);

    console.log(`[done] ${outputPath}`);
    console.log(
      `[done] ${verification.stream.width}x${verification.stream.height}, `
      + `${verification.stream.codec_name}/${verification.stream.pix_fmt}, `
      + `${verification.duration.toFixed(2)} seconds`,
    );
  } finally {
    if (watchdog) clearTimeout(watchdog);
    await browser?.close().catch(() => undefined);
    await rm(workDirectory, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
