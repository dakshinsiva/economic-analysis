import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/** External links: hrefs are asserted exactly; reachability is best-effort here (hosts throttle
 * automated clients) and verified separately by the docs link checker. Only a definite 404/410 fails. */
async function alive(request: APIRequestContext, url: string) {
  try {
    const r = await request.get(url, { headers: { "user-agent": "Mozilla/5.0 (link audit)" }, maxRedirects: 5, timeout: 15_000 });
    return ![404, 410].includes(r.status());
  } catch {
    return true;
  }
}

/**
 * Every button and link in demo mode, exercised once. Fails on any console error.
 * Live-only controls (re-plan, edit steps, follow-ups, watchlist) are covered by scripts/audit-live.mjs.
 */
const errors: string[] = [];
const seenDialogs: string[] = [];

test.beforeEach(async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|ERR_CONNECTION|502|503|Failed to load resource/.test(m.text())) errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("dialog", async (d) => { seenDialogs.push(d.message()); await d.accept(); });
});

async function runReplay(page: Page) {
  await page.getByRole("button", { name: /latest JOLTS report/ }).click();
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
}

test("header, command line, dashboard, series card", async ({ page, request }) => {
  await page.goto("/?demo=1&autoplay=0");
  // header link
  const gh = page.getByRole("link", { name: "GitHub ↗" });
  await expect(gh).toHaveAttribute("href", "https://github.com/dakshinsiva/macrodesk");
  expect(await alive(request, "https://github.com/dakshinsiva/macrodesk")).toBe(true);

  // command line: ⌘K focuses, series mnemonic opens a card, esc closes
  await page.keyboard.press("Meta+k");
  await expect(page.getByPlaceholder(/series id/)).toBeFocused();
  await page.keyboard.type("JTSQUR");
  await expect(page.getByRole("option").first()).toBeVisible();            // suggestions dropdown
  await page.keyboard.press("Enter");
  const card = page.getByRole("dialog", { name: /JTSQUR series card/ });
  await expect(card).toBeVisible();
  await expect(card.getByRole("link", { name: /FRED/ })).toHaveAttribute("href", "https://fred.stlouisfed.org/series/JTSQUR");
  await card.getByRole("button", { name: "close" }).click();
  await expect(card).toBeHidden();

  // slash commands: /help shows the shortcuts dialog; an unsupported one shows a notice
  await page.keyboard.press("Meta+k"); await page.keyboard.type("/help"); await page.keyboard.press("Enter");
  expect(seenDialogs.some((d) => /⌘K/.test(d))).toBe(true);
  await page.keyboard.press("Meta+k"); await page.keyboard.type("/prefs"); await page.keyboard.press("Enter");
  await expect(page.getByText(/needs a live backend/)).toBeVisible();

  // dashboard: collapse/expand, tile opens a card, Esc closes it
  await page.getByRole("button", { name: /Macro dashboard/ }).click();
  await expect(page.getByText("Unemployment", { exact: true })).toBeHidden();
  await page.getByRole("button", { name: /Macro dashboard/ }).click();
  await page.getByRole("button", { name: /Unemployment/ }).first().click();
  await expect(page.getByRole("dialog", { name: /UNRATE series card/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
  // series card quick actions trigger the replay in demo mode
  await page.getByRole("button", { name: /Quits rate/ }).first().click();
  await page.getByRole("button", { name: /Ask about JTSQUR/ }).click();
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible({ timeout: 10_000 });
  expect(errors).toEqual([]);
});

test("plan review: approve, re-plan notice, collapse; evidence, chart, answer, trace, footer", async ({ page, request }) => {
  await page.goto("/?demo=1&autoplay=0");
  await runReplay(page);
  // Re-plan with feedback shows the demo notice and continues
  await page.getByPlaceholder(/or give feedback/).fill("use 10 years");
  await page.getByRole("button", { name: "Re-plan" }).click();
  await expect(page.getByText(/Recorded run: with a backend attached/)).toBeVisible();
  await expect(page.getByText("Every figure traces to fetched evidence.")).toBeVisible({ timeout: 40_000 });

  // plan collapses after fetch; header toggles it
  const planHeader = page.getByRole("button", { name: /steps · (show|hide)/ });
  await expect(planHeader).toContainText("show");
  await planHeader.click(); await expect(planHeader).toContainText("hide");
  await planHeader.click(); await expect(planHeader).toContainText("show");

  // evidence: expand, table rendered, raw toggle, copy
  const evHeader = page.getByRole("button", { name: /tool results?, fetched deterministically/ });
  await evHeader.click();
  await expect(page.locator("table").first()).toBeVisible();
  await page.getByRole("button", { name: "raw" }).first().click();
  await expect(page.locator("pre").filter({ hasText: /units ->/ }).first()).toBeVisible();
  await page.getByRole("button", { name: "copy", exact: true }).first().click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain("JTSJOL");

  // chart exports produce downloads
  const chartCsv = page.waitForEvent("download");
  await page.getByRole("button", { name: "csv" }).first().click();
  expect((await chartCsv).suggestedFilename()).toMatch(/\.csv$/);
  const chartPng = page.waitForEvent("download");
  await page.getByRole("button", { name: "png" }).first().click();
  expect((await chartPng).suggestedFilename()).toMatch(/\.png$/);

  // answer: copy md, download, sources open a card
  await page.getByRole("button", { name: "copy md" }).click();
  await expect(page.getByRole("button", { name: "copied" })).toBeVisible();
  const md = page.waitForEvent("download");
  await page.getByRole("button", { name: "download", exact: true }).click();
  expect((await md).suggestedFilename()).toMatch(/\.md$/);
  await page.getByRole("button", { name: "JTSJOL", exact: true }).first().click();
  await expect(page.getByRole("dialog", { name: /JTSJOL series card/ })).toBeVisible();
  await page.keyboard.press("Escape");
  // citation links inside the answer point at FRED
  const cite = page.getByRole("link", { name: "JTSQUR" }).first();
  await expect(cite).toHaveAttribute("href", /fred\.stlouisfed\.org\/series\/JTSQUR/);
  expect(await alive(request, "https://fred.stlouisfed.org/series/JTSQUR")).toBe(true);

  // trace toggles raw state
  await page.getByRole("button", { name: /show raw state/ }).click();
  await expect(page.getByText(/"revisions":/)).toBeVisible();
  await page.getByRole("button", { name: /hide raw state/ }).click();

  // after a recorded run: Replay and the live link
  await expect(page.getByRole("link", { name: /Run it live/ })).toHaveAttribute("href", /macrodesk#running-it/);
  // footer links resolve
  for (const [name, re] of [["Source on GitHub", /github\.com\/dakshinsiva\/macrodesk$/], ["Debugging log", /02-debugging\.md/], ["Data: FRED", /fred\.stlouisfed\.org/]] as const) {
    const a = page.getByRole("link", { name: new RegExp(name) });
    const href = await a.getAttribute("href");
    expect(href).toMatch(re);
    expect(await alive(request, href!)).toBe(true);
  }
  await page.getByRole("button", { name: "Replay" }).click();
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible({ timeout: 10_000 });
  // sidebar "new" resets to the landing state
  await page.getByRole("button", { name: "new" }).click();
  await expect(page.getByRole("heading", { name: "Research desk" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("jump-to-latest appears when scrolled up during a run", async ({ page }) => {
  await page.goto("/?demo=1&autoplay=0");
  await runReplay(page);
  await page.getByRole("button", { name: "Approve" }).click();
  await page.waitForTimeout(1500);
  await page.locator("main").evaluate((m) => m.scrollTo({ top: 0 }));
  await page.mouse.move(400, 400); await page.mouse.wheel(0, -200);
  await expect(page.getByRole("button", { name: /jump to latest/ })).toBeVisible({ timeout: 5_000 });
  await page.getByRole("button", { name: /jump to latest/ }).click();
  await expect(page.getByRole("button", { name: /jump to latest/ })).toBeHidden({ timeout: 5_000 });
  expect(errors).toEqual([]);
});
