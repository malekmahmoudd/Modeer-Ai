/* Run only against tools.qa_server with disposable data. */
const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const url = process.env.QA_URL || "http://localhost:3015";
(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    const ready = page.waitForResponse(r => r.url().endsWith("/api/auth/status") && r.ok());
    await page.goto(`${url}/login`);
    await ready;
    await page.getByRole("button", { name: /invitation key/i }).click();
    await page.fill("#access-key", "q".repeat(40));
    await page.getByRole("button", { name: /meet your team/i }).click();
    await page.waitForURL(`${url}/`);
    // Own the fixture: this script must pass on an empty database as well.
    const created = await page.evaluate(async () => {
      const response = await fetch("/api/cv", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "CV session regression fixture" }),
      });
      return response.ok;
    });
    assert.equal(created, true, "Could not create the isolated CV fixture");
    await page.goto(`${url}/cv`);
    await page.getByLabel("Your name").fill("Session cleanup regression");
    await page.getByRole("link", { name: "Ask Harvey to review", exact: true }).click();
    await page.waitForURL(/agents\/career/);
    await page.goBack();
    await page.getByLabel("Your name").waitFor();
    assert.equal(await page.getByLabel("Your name").inputValue(), "Session cleanup regression");
    console.log("PASS CV recovery across navigation");
    await page.getByText("Recovered unsaved edits from this browser. Save to keep them on your account.").waitFor();
    console.log("PASS recovery notice explains unsaved state");
    page.once("dialog", d => d.accept());
    await page.reload();
    await page.getByLabel("Your name").waitFor();
    assert.equal(await page.getByLabel("Your name").inputValue(), "Session cleanup regression");
    console.log("PASS CV recovery across reload");
    // A 401 during Save must clear recovery data and leave without a discard prompt.
    await page.getByLabel("Your name").fill("Expired session edit");
    const status = await page.evaluate(async () => (await fetch("/api/auth/sign-out-everywhere", { method: "POST" })).status);
    assert.equal(status, 200);
    let prompts = 0;
    page.on("dialog", d => { prompts++; void d.dismiss(); });
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page.waitForURL(/\/login/);
    assert.equal(prompts, 0);
    assert.equal(await page.evaluate(() => Object.keys(localStorage).some(k => k.startsWith("fareeq.draft"))), false);
    console.log("PASS expired session clears CV draft without a blocking prompt");
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
