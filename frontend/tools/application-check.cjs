/* Run ONLY against tools.qa_server and a disposable database, never user data.
   Start the frontend on 3300, QA API on 8102 with --frontend http://localhost:3300.
   PLAYWRIGHT_MODULE can point to an existing Playwright installation.
   The API bridge buffers streams: this checks UI state, not streaming latency. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    let hold = false, held = false, release, failNew = false;
    const queued = new Promise((resolve) => { release = resolve; });
    await context.route("**/api/**", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (failNew && url.pathname === "/api/conversations" && request.method() === "POST") {
        return route.abort("failed");
      }
      const response = await route.fetch({ url: `http://127.0.0.1:8102${url.pathname}${url.search}` });
      if (hold && !held && url.pathname === "/api/memory/shared" && request.method() === "GET") {
        held = true;
        await queued;
      }
      await route.fulfill({ response });
    });
    await page.goto("http://localhost:3300/login");
    await page.getByRole("button", { name: "Have an invitation key? Use it instead" }).click();
    await page.getByLabel("Access key").fill("q".repeat(40));
    await page.getByRole("button", { name: "Meet your team" }).click();
    await page.waitForURL("http://localhost:3300/");
    await page.goto("http://localhost:3300/memory");
    await page.getByRole("button", { name: "Add something", exact: true }).waitFor();
    assert(await page.getByText(/tries to filter sensitive details, but can miss them/).count());
    const suffix = Date.now();
    const second = `Second regression fact ${suffix}`;
    async function add(key, value) {
      await page.getByRole("button", { name: "Add something", exact: true }).click();
      await page.getByLabel("Label", { exact: true }).fill(key);
      await page.getByLabel("Value", { exact: true }).fill(value);
      await page.getByRole("button", { name: "Save", exact: true }).click();
      await page.getByRole("button", { name: "Add something", exact: true }).waitFor();
    }
    hold = true;
    await add(`first_${suffix}`, `First regression fact ${suffix}`);
    for (let i = 0; !held && i < 100; i++) await page.waitForTimeout(20);
    assert(held, "The first post-save fetch must be intercepted");
    await add(`second_${suffix}`, second);
    await page.getByText(second, { exact: true }).waitFor();
    release();
    await page.waitForTimeout(300);
    assert.equal(await page.getByText(second, { exact: true }).count(), 1);
    console.log("PASS reversed memory responses preserve the newest saved fact");

    await page.setViewportSize({ width: 390, height: 1000 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    console.log("PASS updated privacy wording and phone-width layout");

    await page.goto("http://localhost:3300/agents/study");
    const newButton = page.getByRole("button", { name: "Start a new conversation" });
    await newButton.waitFor();
    await newButton.click();
    await page.waitForTimeout(300);
    const count = () => page.evaluate(async () => (await (await fetch("/api/conversations?agent_id=study")).json()).length);
    const before = await count();
    await page.locator("textarea").fill("Keep this draft");
    failNew = true;
    await newButton.click();
    const notice = page.getByRole("alert").filter({ hasText: "Could not start a new conversation" });
    await notice.first().waitFor();
    assert.equal(await page.locator("textarea").inputValue(), "Keep this draft");
    assert.equal(await count(), before);
    assert.deepEqual(errors, []);
    failNew = false;
    await newButton.click();
    await page.waitForFunction(() => !Array.from(document.querySelectorAll('[role="alert"]')).some(
      (el) => el.textContent.includes("Could not start a new conversation"),
    ));
    for (let i = 0; await count() !== before + 1 && i < 100; i++) await page.waitForTimeout(20);
    assert.equal(await count(), before + 1);
    console.log("PASS failed new conversation preserves state, shows notice and retries successfully");
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error(e); process.exitCode = 1; });
