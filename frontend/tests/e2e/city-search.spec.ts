import { expect, test } from "@playwright/test";

const modes = ["flight", "train", "bus"] as const;

for (const mode of modes) {
  test(`${mode}: city fields use live searchable suggestions`, async ({ page }) => {
    await page.goto(`/?mode=${mode}`);

    const origin = page.getByRole("combobox", { name: "مبدا" });
    await origin.click();
    await expect(page.getByRole("listbox", { name: "انتخاب مبدا" })).toBeVisible();
    await origin.fill("تهران");
    const tehran = page.getByRole("option").filter({ hasText: "تهران" }).first();
    await expect(tehran).toBeVisible();
    await tehran.click();
    await expect(origin).toHaveValue("تهران");

    const destination = page.getByRole("combobox", { name: "مقصد" });
    await destination.fill("اصف");
    const isfahan = page.getByRole("option").filter({ hasText: "اصفهان" }).first();
    await expect(isfahan).toBeVisible();
    await isfahan.click();
    await expect(destination).toHaveValue("اصفهان");
  });
}
