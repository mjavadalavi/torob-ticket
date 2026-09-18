import { expect, test } from "@playwright/test";

const responsiveWidths = [320, 360, 390, 414, 760, 761, 800, 900, 901, 935, 1024, 1100, 1280, 1440] as const;

async function expectNoHorizontalOverflow(page: import("@playwright/test").Page, width: number) {
  await expect.poll(() => page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }))).toEqual({ clientWidth: width, scrollWidth: width });
}

function shiftIsoDate(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

test("round-trip return date must be later than the departure date", async ({ page }) => {
  await page.goto("/?mode=flight");
  await page.getByRole("button", { name: "رفت‌وبرگشت", exact: true }).click();
  await page.getByRole("button", { name: "انتخاب تاریخ رفت و برگشت" }).click();

  const dialog = page.getByRole("dialog", { name: "انتخاب تاریخ" });
  const calendar = dialog.locator(".calendar-grid:not(.calendar-weekdays)");
  const selectedDeparture = calendar.locator("button.selected").first();
  const departureLabel = await selectedDeparture.innerText();

  await selectedDeparture.click();
  await expect(dialog).toContainText("حالا یک تاریخ بعد از رفت را برای برگشت انتخاب کنید");
  await expect(calendar.locator("button.selected").first()).toBeDisabled();
  await expect(calendar.locator("button.selected").first()).toHaveAttribute(
    "title",
    "تاریخ برگشت باید بعد از تاریخ رفت باشد",
  );

  const nextAvailableDate = calendar.locator("button:not(:disabled)").filter({ hasNotText: departureLabel }).first();
  await nextAvailableDate.click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: "انتخاب تاریخ رفت و برگشت" })).not.toContainText("انتخاب");
});

test("dates before today are visibly gray and cannot be selected", async ({ page }) => {
  await page.goto("/?mode=flight");
  await page.getByRole("button", { name: "انتخاب تاریخ رفت" }).click();

  const dialog = page.getByRole("dialog", { name: "انتخاب تاریخ" });
  const calendar = dialog.locator(".calendar-grid:not(.calendar-weekdays)");
  await dialog.getByRole("button", { name: "ماه قبل" }).click();

  const firstDay = calendar.getByRole("button", { name: "۱", exact: true });
  await expect(firstDay).toBeDisabled();
  await expect(firstDay).toHaveClass(/past/);
  await expect(firstDay).toHaveAttribute("title", "تاریخ‌های قبل از امروز قابل انتخاب نیستند");
  await expect(firstDay).toHaveCSS("color", "rgb(167, 177, 191)");
});

test("future dates before the current selection remain available for departure", async ({ page }) => {
  await page.goto("/?mode=flight");
  await page.getByRole("button", { name: "انتخاب تاریخ رفت" }).click();

  const dialog = page.getByRole("dialog", { name: "انتخاب تاریخ" });
  const calendar = dialog.locator(".calendar-grid:not(.calendar-weekdays)");
  const today = await calendar.locator("button.today").getAttribute("data-date");
  expect(today).not.toBeNull();
  const futureDate = shiftIsoDate(today!, 7);
  let futureDateButton = calendar.locator(`button[data-date="${futureDate}"]`);
  if (await futureDateButton.count() === 0) {
    await dialog.getByRole("button", { name: "ماه بعد" }).click();
    futureDateButton = calendar.locator(`button[data-date="${futureDate}"]`);
  }
  await futureDateButton.click();
  await page.getByRole("button", { name: "انتخاب تاریخ رفت" }).click();

  const previousDate = shiftIsoDate(futureDate, -1);
  const previousDateButton = calendar.locator(`button[data-date="${previousDate}"]`);
  if (await previousDateButton.count() === 0) {
    await dialog.getByRole("button", { name: "ماه قبل" }).click();
  }
  await expect(calendar.locator(`button[data-date="${previousDate}"]`)).toBeEnabled();
});

test("compact header stays on one row at tablet width", async ({ page }) => {
  await page.setViewportSize({ width: 935, height: 720 });
  await page.goto(`/offers/${"expired-offer"}`);
  await expect(page.getByRole("heading", { name: "این نتیجه دیگر تازه نیست" })).toBeVisible();

  const layout = await page.locator(".site-header.compact").evaluate((header) => {
    const headerRect = header.getBoundingClientRect();
    const children = Array.from(header.querySelectorAll(".logo-link,.global-search,.new-search,.login"));
    return {
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      allInsideHeader: children.every((child) => {
        const rect = child.getBoundingClientRect();
        return rect.top >= headerRect.top && rect.bottom <= headerRect.bottom;
      }),
    };
  });

  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.clientWidth);
  expect(layout.allInsideHeader).toBe(true);
});

test("home search stays usable across modes and responsive breakpoints", async ({ page }) => {
  for (const mode of ["flight", "train", "bus"] as const) {
    for (const width of responsiveWidths) {
      await page.setViewportSize({ width, height: width <= 414 ? 844 : 900 });
      await page.goto(`/?mode=${mode}`);
      await expect(page.locator(".ticket-search")).toBeVisible();
      await expect(page.getByRole("button", { name: "جستجو", exact: true })).toBeVisible();
      await expectNoHorizontalOverflow(page, width);
    }
  }
});

test("home popovers stay inside mobile, tablet, and desktop viewports", async ({ page }) => {
  for (const width of [320, 761, 1440] as const) {
    await page.setViewportSize({ width, height: width === 320 ? 800 : 900 });
    await page.goto("/?mode=flight");
    await page.getByRole("button", { name: "رفت‌وبرگشت", exact: true }).click();
    await page.getByRole("button", { name: "انتخاب تاریخ رفت و برگشت" }).click();
    await expect(page.getByRole("dialog", { name: "انتخاب تاریخ" })).toBeVisible();
    await expectNoHorizontalOverflow(page, width);
    await page.getByRole("button", { name: "بستن", exact: true }).click();

    await page.getByRole("combobox", { name: "تعداد مسافر" }).click();
    await expect(page.getByRole("dialog", { name: "انتخاب تعداد مسافر" })).toBeVisible();
    await expectNoHorizontalOverflow(page, width);
    await page.getByRole("button", { name: "تأیید", exact: true }).click();

    const origin = page.getByRole("combobox", { name: "مبدا" });
    await origin.fill("ته");
    await expect(page.getByRole("listbox", { name: "انتخاب مبدا" })).toBeVisible();
    await expectNoHorizontalOverflow(page, width);
    await page.keyboard.press("Escape");
  }
});

test("train compartment control stays usable at responsive boundaries", async ({ page }) => {
  for (const width of [320, 900, 901, 1100, 1440] as const) {
    await page.setViewportSize({ width, height: width === 320 ? 800 : 900 });
    const tripTypeBounds = () => page.locator(".trip-type").evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
    });
    await page.goto("/?mode=flight");
    const flightTripTypeBounds = await tripTypeBounds();
    await page.getByRole("link", { name: "قطار", exact: true }).click();
    const checkbox = page.getByRole("checkbox", { name: "کوپه دربست" });
    await expect(checkbox).toBeVisible();
    expect(await tripTypeBounds()).toEqual(flightTripTypeBounds);
    await expectNoHorizontalOverflow(page, width);
    const controlGap = await page.locator(".search-head").evaluate((header) => {
      const checkboxRect = header.querySelector(".train-compartment-check")!.getBoundingClientRect();
      const tripTypeRect = header.querySelector(".trip-type")!.getBoundingClientRect();
      const headerRect = header.getBoundingClientRect();
      const tabRects = Array.from(header.querySelectorAll(".mode-tabs a"), (tab) => tab.getBoundingClientRect());
      const tabsLeft = Math.min(...tabRects.map((rect) => rect.left));
      const tabsRight = Math.max(...tabRects.map((rect) => rect.right));
      return {
        horizontal: Math.round(tripTypeRect.left - checkboxRect.right),
        vertical: Math.round(Math.abs(
          tripTypeRect.top + tripTypeRect.height / 2
          - (checkboxRect.top + checkboxRect.height / 2),
        )),
        tabsCenter: Math.round(Math.abs(
          (tabsLeft + tabsRight) / 2
          - (headerRect.left + headerRect.width / 2),
        )),
        rightEdge: Math.round(Math.abs(headerRect.right - tripTypeRect.right)),
      };
    });
    expect(controlGap.horizontal).toBeGreaterThanOrEqual(0);
    expect(controlGap.horizontal).toBeLessThanOrEqual(12);
    expect(controlGap.vertical).toBeLessThanOrEqual(1);
    expect(controlGap.tabsCenter).toBeLessThanOrEqual(1);
    expect(controlGap.rightEdge).toBeLessThanOrEqual(1);
    await checkbox.check();
    await expect(checkbox).toBeChecked();
    await page.getByRole("link", { name: "اتوبوس", exact: true }).click();
    expect(await tripTypeBounds()).toEqual(flightTripTypeBounds);
  }
});
