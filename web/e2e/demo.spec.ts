import { expect, test } from "@playwright/test";

// The recorded replay is what every visitor sees first; this guards the whole pipeline rendering.
test("demo replay runs plan -> review -> evidence -> chart -> critic -> answer", async ({ page }) => {
  await page.goto("/?demo=1&autoplay=0");
  await page.getByRole("button", { name: /latest JOLTS report/ }).click();
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Every figure traces to fetched evidence.")).toBeVisible({ timeout: 40_000 });
  await expect(page.getByText("JOLTS: Job Openings", { exact: false }).first()).toBeVisible();
  await expect(page.locator("text=ANSWER").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /JTSJOL/ }).first()).toHaveAttribute("href", /fred\.stlouisfed\.org\/series\/JTSJOL/);
});

test("autoplay starts on arrival and the review countdown can be taken over", async ({ page }) => {
  await page.goto("/?demo=1");
  await expect(page.getByText(/auto-approving in/)).toBeVisible({ timeout: 10_000 });
  await page.getByPlaceholder(/or give feedback/).focus();
  await expect(page.getByText(/auto-approving in/)).toBeHidden();
});
