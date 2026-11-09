/* End-to-end browser checks against a running server + timer worker.
 *
 *   NODE_PATH=$(npm root -g) node e2e/run_flows.cjs [base-url]
 *
 * Uses Playwright (Chromium). Writes screenshots and a JSON report to
 * e2e/artifacts/. Exits non-zero if any check fails.
 */
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const BASE = process.argv[2] || process.env.E2E_BASE_URL || "http://127.0.0.1:8000";
const OUT = path.join(__dirname, "artifacts");
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const T = 9000; // polling is 2.5s; allow a few cycles

function log(ok, name, detail = "") {
  results.push({ ok, name, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? " — " + detail : ""}`);
}
async function check(name, fn) {
  try {
    const detail = await fn();
    log(true, name, detail || "");
  } catch (err) {
    log(false, name, String(err && err.message ? err.message : err).split("\n")[0]);
  }
}
const card = (page, text) => page.locator("article.task", { hasText: text });
async function toast(page, text) {
  await page.locator(".toast", { hasText: text }).first().waitFor({ timeout: T });
}
async function pickTable(page, label) {
  const ok = await page.evaluate((label) => {
    for (const span of document.querySelectorAll(".table-picker span")) {
      if (span.firstChild && span.firstChild.textContent.trim() === label) { span.click(); return true; }
    }
    return false;
  }, label);
  if (!ok) throw new Error(`table ${label} not in picker`);
}
async function startDemo(browser, profile) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(BASE + "/demo/");
  await page.check(`input[name=profile][value=${profile}]`);
  await page.click("text=Start the demo");
  await page.waitForURL("**/demo/floor/");
  const personas = Object.fromEntries(
    await page.$$eval(".persona", (as) => as.map((a) => [a.querySelector("b").textContent, a.getAttribute("href")]))
  );
  return { ctx, floor: page, personas };
}
async function open(ctx, personas, who, viewport) {
  const page = await ctx.newPage();
  if (viewport) await page.setViewportSize(viewport);
  page.on("pageerror", (e) => log(false, `no JS errors (${who})`, String(e)));
  await page.goto(BASE + personas[who]);
  return page;
}
async function csrfPost(page, url, form) {
  return page.evaluate(async ({ url, form }) => {
    const token = document.querySelector('meta[name="csrf-token"]').content;
    const res = await fetch(url, {
      method: "POST",
      body: new URLSearchParams(form),
      headers: { "X-CSRFToken": token, "X-Dispatch-Fetch": "1" },
    });
    return { status: res.status, body: await res.json() };
  }, { url, form });
}

(async () => {
  const browser = await chromium.launch();

  // ------------------------------------------------------------ homepage
  for (const [name, viewport] of [["desktop", { width: 1440, height: 900 }], ["mobile", { width: 390, height: 844 }]]) {
    await check(`homepage renders at ${name} width`, async () => {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      await page.goto(BASE + "/");
      await page.getByRole("heading", { level: 1 }).filter({ hasText: "Get food off the pass." }).waitFor();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
      if (overflow > 0) throw new Error(`horizontal overflow ${overflow}px`);
      await page.screenshot({ path: path.join(OUT, `home-${name}.png`), fullPage: name === "desktop" });
      // Interactive component: the hero card responds.
      await page.locator("[data-walkthrough] button", { hasText: "Claim" }).click();
      await page.locator("[data-walkthrough] .chip", { hasText: "You have it" }).waitFor();
      // Preset tabs.
      await page.getByRole("tab", { name: "Coordinated Service" }).click();
      await page.locator("#panel-coordinated_service", { hasText: "Team ready" }).waitFor();
      if (errors.length) throw new Error(errors.join("; "));
      // Primary action leads to a usable demo.
      await page.getByRole("link", { name: "Try the demo" }).first().click();
      await page.waitForURL("**/demo/");
      await page.close();
      return `no overflow, no console errors`;
    });
  }

  // ------------------------------------------------------------ regular service
  const reg = await startDemo(browser, "regular");
  const P = reg.personas;
  await reg.floor.waitForTimeout(1500);
  await reg.floor.screenshot({ path: path.join(OUT, "demo-floor-regular.png"), fullPage: true });
  const phone = { width: 390, height: 844 };
  const sam = await open(reg.ctx, P, "Sam", phone);
  const maria = await open(reg.ctx, P, "Maria", phone);
  const ana = await open(reg.ctx, P, "Ana", phone);
  const lee = await open(reg.ctx, P, "Lee", phone);

  await check("regular: Expo → Runner → Delivered", async () => {
    await pickTable(sam, "4");
    await sam.fill("#items", "3");
    await sam.getByRole("button", { name: "Food ready" }).click();
    await toast(sam, "Food ready: Table 4 · 3 plates");
    const offer = card(maria, "Table 4 · 3 plates");
    await offer.locator(".chip", { hasText: "Offered to you" }).waitFor({ timeout: T });
    await maria.screenshot({ path: path.join(OUT, "runner-offer-mobile.png") });
    await offer.getByRole("button", { name: "Claim" }).click();
    await toast(maria, "Claimed");
    await card(maria, "Table 4 · 3 plates").getByRole("button", { name: "Delivered" }).click();
    await toast(maria, "Delivered");
    await card(sam, "Table 4 · 3 plates").locator(".chip", { hasText: "Delivered" }).waitFor({ timeout: T });
    return "expo saw Delivered via live polling";
  });

  await check("reset: Vacated → Busser → Ready to seat → seated", async () => {
    const tile = ana.locator('[data-table="1"]');
    await tile.locator("summary", { hasText: "Party has left" }).click();
    await tile.getByRole("button", { name: "Yes, they've left" }).click();
    await toast(ana, "party left");
    await ana.locator('[data-table="1"] .chip', { hasText: "Needs reset" }).waitFor({ timeout: T });
    const reset = card(lee, "Reset table 1");
    await reset.getByRole("button", { name: "Claim" }).click({ timeout: T });
    await toast(lee, "Claimed");
    await ana.locator('[data-table="1"] .chip', { hasText: "Being reset" }).waitFor({ timeout: T });
    await card(lee, "Reset table 1").getByRole("button", { name: "Table reset done" }).click();
    await ana.locator('[data-table="1"] .chip', { hasText: "Ready to seat" }).waitFor({ timeout: T });
    await ana.screenshot({ path: path.join(OUT, "host-tables-mobile.png"), fullPage: true });
    await ana.locator('[data-table="1"] summary', { hasText: "Seat party" }).click();
    await ana.locator('[data-table="1"]').getByRole("button", { name: "4", exact: true }).click();
    await ana.locator('[data-table="1"] .chip', { hasText: "Seated" }).waitFor({ timeout: T });
    return "host view updated after busser confirmed";
  });

  await check("roles: runner cannot open manager screens (server 403)", async () => {
    const sid = P["Maria"].split("/")[2];
    const api = await csrfPost(maria, `${BASE}/app/${sid}/act/seat_override/`, { table: "1", party: "2" });
    if (api.status !== 403) throw new Error(`override status ${api.status}`);
    const res = await maria.goto(`${BASE}/app/${sid}/manage/`);
    if (res.status() !== 403) throw new Error(`status ${res.status()}`);
    await maria.goto(BASE + P["Maria"]);
    return "403 page and 403 JSON";
  });

  await check("unconfirmed action is flagged and reconciled after reconnect", async () => {
    await pickTable(sam, "5");
    await sam.getByRole("button", { name: "Food ready" }).click();
    await toast(sam, "Table 5");
    const offline = await reg.ctx.browser().newContext({ viewport: phone, storageState: await reg.ctx.storageState() });
    const m2 = await offline.newPage();
    await m2.goto(BASE + P["Maria"]);
    const offer = card(m2, "Table 5");
    await offer.getByRole("button", { name: "Claim" }).waitFor({ timeout: T });
    await offline.setOffline(true);
    await offer.getByRole("button", { name: "Claim" }).click();
    await m2.locator("[data-unconfirmed]", { hasText: "Not confirmed" }).waitFor({ timeout: T });
    await m2.screenshot({ path: path.join(OUT, "unconfirmed-mobile.png") });
    const conn = await m2.locator("[data-conn]").textContent();
    if (!/Offline/.test(conn)) throw new Error(`connection indicator said ${conn}`);
    await offline.setOffline(false);
    await m2.locator("[data-unconfirmed]", { hasText: "Back online" }).waitFor({ timeout: T });
    // The claim never reached the server, so the board still shows the offer.
    await card(m2, "Table 5").getByRole("button", { name: "Claim" }).click();
    await toast(m2, "Claimed");
    await offline.close();
    return "banner shown offline, board re-read before retry";
  });

  await check("offer expiration progresses with every browser tab closed", async () => {
    const kim = await open(reg.ctx, P, "Kim");
    const sid = P["Kim"].split("/")[2];
    await kim.goto(`${BASE}/app/${sid}/manage/rules/`);
    await kim.fill("#ot", "10");
    await kim.fill("#bt", "10");
    await kim.getByRole("button", { name: "Save rules" }).click();
    await kim.locator(".notice", { hasText: "Saved" }).waitFor();
    await sam.reload();
    await pickTable(sam, "6");
    await sam.getByRole("button", { name: "Food ready" }).click();
    await toast(sam, "Table 6");
    const state = await reg.ctx.storageState();
    await reg.ctx.close(); // every tab of this session is gone
    const started = Date.now();
    await new Promise((r) => setTimeout(r, 25000));
    const ctx2 = await browser.newContext({ viewport: phone, storageState: state });
    const rae = await ctx2.newPage();
    await rae.goto(BASE + P["Rae"]);
    const escalated = card(rae, "Table 6");
    await escalated.locator(".chip", { hasText: "With floor lead" }).waitFor({ timeout: T });
    await rae.screenshot({ path: path.join(OUT, "lead-escalated-mobile.png"), fullPage: true });
    const kim2 = await ctx2.newPage();
    await kim2.goto(`${BASE}/app/${sid}/manage/activity/?type=offer`);
    const log = await kim2.locator(".log").textContent();
    if (!/Timer/.test(log) || !/didn't claim Table 6/.test(log)) throw new Error("activity log lacks timer expiries");
    await kim2.goto(`${BASE}/app/${sid}/manage/`);
    await kim2.screenshot({ path: path.join(OUT, "manager-now.png"), fullPage: true });
    await escalated.getByRole("combobox").selectOption({ label: "Dev" });
    await escalated.getByRole("button", { name: "Assign to" }).click();
    await toast(rae, "Assigned");
    await ctx2.close();
    return `primary → backup → floor lead in ${Math.round((Date.now() - started) / 1000)}s with no tabs open`;
  });

  // ------------------------------------------------------------ fine dining
  const fine = await startDemo(browser, "pairing_coordination");
  const F = fine.personas;
  const noor = await open(fine.ctx, F, "Noor", phone);
  const elise = await open(fine.ctx, F, "Elise", phone);
  const jordan = await open(fine.ctx, F, "Jordan", phone);
  const mateo = await open(fine.ctx, F, "Mateo", phone);

  await check("fine dining: course held, invisible to runner, pairing blocks release", async () => {
    await pickTable(noor, "3");
    await noor.getByRole("button", { name: "Stage course" }).click();
    await toast(noor, "Staged Table 3 · Course 1");
    const staged = card(elise, "Table 3 · Course 1");
    await staged.locator(".blockers", { hasText: "Can't release yet" }).waitFor({ timeout: T });
    if (!(await staged.getByRole("button", { name: "Release" }).isDisabled())) throw new Error("release button enabled");
    await mateo.waitForTimeout(3000);
    if (await card(mateo, "Table 3").count()) throw new Error("runner can see a staged course");
    const sid = F["Elise"].split("/")[2];
    const taskId = await staged.getAttribute("data-task");
    const api = await csrfPost(elise, `${BASE}/app/${sid}/act/release_course/`, { task: taskId });
    if (api.status !== 409 || !/Can't release yet/.test(api.body.message)) throw new Error(`server allowed early release: ${api.status}`);
    await elise.screenshot({ path: path.join(OUT, "captain-blocked-mobile.png"), fullPage: true });
    return "button disabled and server refused (409)";
  });

  await check("fine dining: sommelier confirms, captain releases, runner delivers", async () => {
    await card(jordan, "Table 3 · Course 1").getByRole("button", { name: "Pairing ready" }).click({ timeout: T });
    await toast(jordan, "Pairing ready");
    const staged = card(elise, "Table 3 · Course 1");
    await staged.locator(".chip", { hasText: "Pairing ready · Jordan" }).waitFor({ timeout: T });
    await staged.getByRole("button", { name: "Release" }).click();
    await toast(elise, "Released");
    const offer = card(mateo, "Table 3 · Course 1");
    await offer.getByRole("button", { name: "Claim" }).click({ timeout: T });
    await toast(mateo, "Claimed");
    await card(mateo, "Table 3 · Course 1").getByRole("button", { name: "Delivered" }).click();
    await toast(mateo, "Delivered");
    return "pairing recorded with who confirmed it";
  });

  await check("coordinated service: team readiness also required", async () => {
    await fine.floor.reload();
    await fine.floor.selectOption("#preset", "coordinated_service");
    await fine.floor.getByRole("button", { name: "Switch preset" }).click();
    await fine.floor.locator(".notice", { hasText: "Coordinated Service" }).waitFor();
    await noor.reload();
    await pickTable(noor, "5");
    await noor.getByRole("button", { name: "Stage course" }).click();
    await toast(noor, "Staged Table 5");
    await elise.reload();
    const staged = card(elise, "Table 5 · Course 1");
    await card(jordan, "Table 5 · Course 1").getByRole("button", { name: "Pairing ready" }).click({ timeout: T });
    await staged.locator(".blockers", { hasText: "team is ready" }).waitFor({ timeout: T });
    if (!(await staged.getByRole("button", { name: "Release" }).isDisabled())) throw new Error("release enabled before team ready");
    await staged.getByRole("button", { name: "Service team is ready" }).click();
    await toast(elise, "Team ready");
    await card(elise, "Table 5 · Course 1").getByRole("button", { name: "Release" }).click({ timeout: T });
    await toast(elise, "Released");
    return "released only after pairing + team readiness";
  });

  await fine.ctx.close();
  await browser.close();
  fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify({ base: BASE, at: new Date().toISOString(), results }, null, 2));
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} browser checks passed. Artifacts: ${OUT}`);
  process.exit(failed ? 1 : 0);
})().catch((err) => {
  console.error(err);
  process.exit(2);
});
