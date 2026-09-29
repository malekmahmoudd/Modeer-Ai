/* Reminders through a real push service: desktop Chrome subscribes through
   Google's (FCM), the QA API sends an encrypted reminder over the internet,
   and the service worker shows it. Then signing out, removing the device from
   another browser, and signing out everywhere must each stop delivery.

   Not a phone: iOS and Android delivery, the lock screen and battery rules
   need a real device and an https deployment. Needs a production build (the
   service worker only registers there) and network access to FCM:
     cd backend && .venv/bin/python -m tools.qa_server --reset --port 8000 --db ui-qa.db
     cd frontend && npx next build && npx next start -p 3000
     PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/push-live-qa.cjs */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const URL = process.env.QA_URL || "http://localhost:3000";
const KEY = "q".repeat(40);
const results = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function check(name, ok, detail = "") {
  results.push({ name, ok: !!ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}

async function browserProfile(name) {
  // A real profile directory: push needs a persistent profile.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), `fareeq-push-${name}-`));
  const context = await chromium.launchPersistentContext(dir, {
    channel: "chrome",
    headless: true,
    viewport: { width: 1280, height: 860 },
  });
  await context.grantPermissions(["notifications"], { origin: URL });
  const page = context.pages()[0] || (await context.newPage());
  return { context, page, dir };
}

async function signIn(page) {
  await page.goto(`${URL}/login`);
  await page.getByRole("button", { name: /invitation key/i }).click();
  await page.fill("#access-key", KEY);
  await page.getByRole("button", { name: /meet your team/i }).click();
  await page.waitForURL(`${URL}/`);
}

const shown = (page) =>
  page.evaluate(async () => {
    const reg = await navigator.serviceWorker.getRegistration("/");
    return reg ? (await reg.getNotifications()).map((n) => n.body) : [];
  });

async function waitShown(page, count, ms = 25000) {
  const until = Date.now() + ms;
  while (Date.now() < until) {
    if ((await shown(page)).length >= count) return true;
    await sleep(500);
  }
  return false;
}

async function test(page) {
  return page.evaluate(async () => {
    const r = await fetch("/api/push/test", { method: "POST" });
    return r.status;
  });
}

async function turnOn(page) {
  await page.goto(`${URL}/account`);
  await page.waitForFunction(() => navigator.serviceWorker.controller || true);
  await page.evaluate(() => navigator.serviceWorker.ready);
  const box = page.getByLabel("Send me a daily reminder on this device");
  await box.waitFor({ timeout: 10000 });
  await page.waitForFunction(() => !document.querySelector('input[type=checkbox]:disabled') || true);
  await sleep(1500);
  if (!(await box.isChecked())) await box.check();
  await page.getByText(/Reminders are on for this device|can't show reminders|blocked|aren't switched on/).first().waitFor({ timeout: 20000 });
  return (await page.getByText("Reminders are on for this device.").count()) > 0;
}

(async () => {
  const a = await browserProfile("a");
  const b = await browserProfile("b");
  try {
    await signIn(a.page);
    const on = await turnOn(a.page);
    check("Chrome subscribes through the real push service", on);
    if (!on) throw new Error("could not subscribe; the rest needs a subscription");
    const endpoint = await a.page.evaluate(async () => (await (await navigator.serviceWorker.ready).pushManager.getSubscription())?.endpoint);
    check("the subscription is an FCM endpoint", /^https:\/\/fcm\.googleapis\.com\//.test(endpoint || ""), (endpoint || "").slice(0, 45));

    check("a test reminder is accepted by the push service", (await test(a.page)) === 200);
    check("the reminder arrives and is shown", await waitShown(a.page, 1), JSON.stringify(await shown(a.page)));

    // 1. Signing out on this device.
    await a.page.goto(`${URL}/account`);
    await a.page.getByRole("button", { name: "Sign out", exact: true }).click();
    await a.page.waitForURL(/\/login/);
    const localSub = await a.page.evaluate(async () => Boolean(await (await navigator.serviceWorker.ready).pushManager.getSubscription()));
    check("signing out drops the browser's subscription", !localSub);
    await signIn(a.page);
    await a.page.goto(`${URL}/account`);
    await sleep(2500);
    check("after signing back in, reminders show as off", !(await a.page.getByLabel("Send me a daily reminder on this device").isChecked()));
    check("and nothing is sent to it", (await test(a.page)) === 409);

    // 2. Removed from another browser (a lost device).
    check("reminders back on for the next check", await turnOn(a.page));
    await a.page.evaluate(async () => (await (await navigator.serviceWorker.ready).getNotifications()).forEach((n) => n.close()));
    await signIn(b.page);
    await b.page.goto(`${URL}/account`);
    await b.page.getByText("This device", { exact: true }).waitFor({ timeout: 10000 });
    const others = b.page.locator("li", { hasNotText: "This device" }).getByRole("button", { name: /Sign out/ });
    const before = await others.count();
    // Sign out every other device from B (only A is signed in besides B).
    for (let i = 0; i < before; i++) await others.first().click().then(() => sleep(800));
    check("from B, the test reaches no browser (A's reminders ended)", (await test(b.page)) === 409);
    await sleep(8000);
    check("A shows nothing more", (await shown(a.page)).length === 0, JSON.stringify(await shown(a.page)));

    // 3. Sign out everywhere.
    await signIn(a.page);
    check("reminders on again for the last check", await turnOn(a.page));
    await b.page.goto(`${URL}/account`);
    b.page.once("dialog", (d) => d.accept());
    await b.page.getByRole("button", { name: "Sign out every device" }).click();
    await b.page.waitForURL(/\/login/);
    await signIn(b.page);
    check("after signing out everywhere, the test reaches no browser", (await test(b.page)) === 409);
  } catch (e) {
    check("run completed", false, e.message.split("\n")[0]);
  } finally {
    for (const p of [a, b]) {
      await p.context.close();
      fs.rmSync(p.dir, { recursive: true, force: true });
    }
  }
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} passed`);
  process.exit(failed ? 1 : 0);
})();
