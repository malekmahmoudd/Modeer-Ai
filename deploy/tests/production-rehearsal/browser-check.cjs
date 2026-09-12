/* Browser checks against the production rehearsal (see README.md), in installed
   Chrome through Playwright. PLAYWRIGHT_MODULE may point to an existing install.
   REHEARSAL_URL and REHEARSAL_REPORT override the address and the report path. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const base = process.env.REHEARSAL_URL || "https://localhost:8443";
const report = process.env.REHEARSAL_REPORT || "production-rehearsal-results.json";
const KEY_A = "q".repeat(40);
const KEY_B = "r".repeat(40);
// The policy under test is the one in the repository's Caddyfile, not a copy.
const shippedCsp = fs
  .readFileSync(path.join(__dirname, "..", "..", "Caddyfile"), "utf8")
  .match(/Content-Security-Policy "([^"]+)"/)[1];

const results = { url: base, csp: shippedCsp, checks: [], cspViolations: [], pageErrors: [] };
const check = (name) => {
  results.checks.push(name);
  console.log("PASS", name);
};

async function session(browser, viewport) {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport });
  await context.addInitScript(() => {
    window.__csp = [];
    document.addEventListener("securitypolicyviolation", (e) =>
      window.__csp.push(`${e.violatedDirective} blocked ${e.blockedURI || "inline"}`),
    );
  });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (/Content Security Policy/i.test(m.text())) results.cspViolations.push(m.text());
  });
  page.on("pageerror", (e) => results.pageErrors.push(e.message));
  page.on("dialog", (d) => d.accept());
  return { context, page };
}

async function signIn(page, key) {
  await page.goto(base + "/login");
  await page.getByLabel("Access key").fill(key);
  await page.getByRole("button", { name: "Meet your team" }).click();
  await page.waitForURL(base + "/");
}

const sendButton = (page) => page.getByRole("button", { name: "Send message", exact: true });
async function send(page, text) {
  await page.locator("textarea").fill(text);
  await sendButton(page).click();
}
async function settled(page) {
  await sendButton(page).waitFor();
}
const userBubbles = (page, text) => page.locator(".user-message", { hasText: text });
const lastReply = (page) => page.locator(".assistant-message").last();

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const { context, page } = await session(browser, { width: 1440, height: 900 });

    // --- headers, sign-in, every page under the shipped policy ---------------
    const doc = await page.goto(base + "/login");
    const headers = doc.headers();
    assert.equal(headers["content-security-policy"], shippedCsp);
    assert.match(headers["strict-transport-security"] || "", /max-age=\d+/);
    assert.equal(headers["x-frame-options"], "DENY");
    assert.equal(headers["x-content-type-options"], "nosniff");
    check("document carries the Caddyfile CSP and security headers");

    await signIn(page, KEY_A);
    const cookie = (await context.cookies()).find((c) => c.httpOnly);
    assert(cookie && cookie.secure && cookie.sameSite === "Strict", "session cookie flags");
    check("sign-in over HTTPS sets an httpOnly, Secure, SameSite=Strict session");

    for (const route of ["/", "/team", "/memory", "/goals", "/account", "/privacy", "/agents/study"]) {
      await page.goto(base + route);
      await page.waitForLoadState("networkidle");
      await page.locator("main").waitFor();
      const state = await page.evaluate(async () => {
        await document.fonts.ready;
        return {
          brokenImages: [...document.images].filter((i) => !i.complete || i.naturalWidth === 0).map((i) => i.src),
          loadedFonts: [...document.fonts].filter((f) => f.status === "loaded").length,
          bodyFont: getComputedStyle(document.body).fontFamily,
          violations: window.__csp.splice(0),
        };
      });
      assert.deepEqual(state.brokenImages, [], `${route}: images blocked or broken`);
      assert(state.loadedFonts > 0, `${route}: no self-hosted font loaded`);
      assert(!/Times/.test(state.bodyFont), `${route}: stylesheet not applied`);
      results.cspViolations.push(...state.violations.map((v) => `${route}: ${v}`));
    }
    assert.deepEqual(results.cspViolations, [], "CSP violations while rendering pages");
    check("seven pages render with scripts, styles, fonts and images allowed and no violations");

    // --- onboarding -> memory -> follow-up ---------------------------------------
    await page.goto(base + "/agents/modeer?onboarding=1");
    await send(page, "I live in Cairo. I am studying computer science. My native language is Arabic.");
    await page.getByText("A short, useful reply.").first().waitFor();
    await settled(page);
    await page.goto(base + "/memory");
    await page.getByText("Cairo", { exact: true }).waitFor();
    await page.goto(base + "/agents/study");
    await send(page, "qa-recall what do you know about me?");
    await page.getByText("Recall: Cairo.").waitFor();
    await settled(page);
    check("onboarding fact saved, shown in Memory, and in a specialist's prompt");

    // --- streaming through the proxy ------------------------------------------------
    // From the first word to the last, the text must be seen growing. A proxy
    // that buffered the stream would deliver it all at once: one step.
    await send(page, "qa-slow please");
    await lastReply(page).getByText("Here", { exact: false }).waitFor();
    const lengths = new Set();
    for (let i = 0; i < 80; i++) {
      const text = await lastReply(page).innerText();
      lengths.add(text.length);
      if (text.includes("through the proxy.")) break;
      await page.waitForTimeout(100);
    }
    await settled(page);
    assert(lengths.size >= 4, `reply arrived in ${lengths.size} steps; the proxy may be buffering`);
    check(`reply streams progressively through Caddy (${lengths.size} visible steps)`);

    // --- truncated: kept, labelled, survives reload, Continue ------------------------
    await send(page, "qa-truncate please");
    // Scoped to the transcript: the same words are also spoken through the
    // page's live region, which is hidden but still matches a page-wide search.
    const cut = "This reply reached its length limit and may be incomplete.";
    await lastReply(page).getByText(cut).waitFor();
    await page.getByText("This answer is long and runs out of room").waitFor();
    await page.getByRole("button", { name: "Continue", exact: true }).waitFor();
    await page.reload();
    await lastReply(page).getByText(cut).waitFor();
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.getByText("Continue from where you stopped.").waitFor();
    await settled(page);
    await page.getByRole("button", { name: "Continue", exact: true }).waitFor({ state: "detached" });
    check("truncated reply keeps its text, says so after reload, and Continue asks for the rest");

    // --- dropped mid-stream, then retried in place ------------------------------------
    await send(page, "qa-drop-once please");
    const dropped = "The connection to the AI provider dropped before this reply finished.";
    await lastReply(page).getByText(dropped).waitFor();
    await page.getByRole("button", { name: "Try again", exact: true }).click();
    await lastReply(page).getByText(dropped).waitFor({ state: "detached" });
    await settled(page);
    await page.reload();
    await lastReply(page).getByText("A short, useful reply.").waitFor();
    assert.equal(await userBubbles(page, "qa-drop-once").count(), 1, "retry duplicated the message");
    assert.equal(await page.getByText("Half an answer,").count(), 0, "stale partial left behind");
    check("interrupted reply is labelled, and Try again replaces it without duplicating the message");

    // --- provider refuses, then retried --------------------------------------------------
    await send(page, "qa-fail-once please");
    await lastReply(page).getByText("The AI provider could not respond (HTTP 503)", { exact: false }).waitFor();
    await page.getByRole("button", { name: "Try again", exact: true }).click();
    await lastReply(page).getByText("A short, useful reply.").waitFor();
    await settled(page);
    await page.reload();
    await lastReply(page).getByText("A short, useful reply.").waitFor();
    assert.equal(await userBubbles(page, "qa-fail-once").count(), 1, "retry duplicated the message");
    check("failed reply is recorded, and one Try again recovers it");

    // --- Markdown link policy in the rendered reply -----------------------------------
    await send(page, "qa-links please");
    await lastReply(page).getByText("Links:", { exact: false }).waitFor();
    await settled(page);
    // The reply body only: the "Personalised from your saved context" link below it is the app's own.
    const hrefs = await lastReply(page)
      .locator(".prose-ink a")
      .evaluateAll((as) => as.map((a) => a.getAttribute("href")));
    assert.deepEqual(hrefs, ["/memory", "https://example.com/docs"]);
    for (const word of ["sneaky", "script", "slashes"]) await lastReply(page).getByText(word, { exact: false }).waitFor();
    check("only safe Markdown links become links; the rest stay as plain words");

    // --- the person's own connection drops mid-reply -----------------------------------
    await send(page, "qa-slow reconnect");
    await lastReply(page).getByText("Here", { exact: false }).waitFor();
    await context.setOffline(true);
    await page.getByRole("alert").first().waitFor();
    await context.setOffline(false);
    let recorded = false;
    for (let i = 0; i < 20 && !recorded; i++) {
      await page.reload();
      await page.locator("textarea").waitFor();
      recorded =
        (await lastReply(page).getByText("The connection closed before this reply finished.").count()) > 0;
      if (!recorded) await page.waitForTimeout(500);
    }
    assert(recorded, "the server did not record the reply the dropped connection cut off");
    await page.getByRole("button", { name: "Try again", exact: true }).click();
    await lastReply(page).getByText("through the proxy.", { exact: false }).waitFor();
    await settled(page);
    assert.equal(await userBubbles(page, "qa-slow reconnect").count(), 1);
    check("after a dropped connection, a reload shows what arrived and Try again finishes it");

    // --- blank messages are refused before any work ----------------------------------
    const blank = await page.request.post(base + "/api/agents/study/chat/stream", {
      data: { message: "  \n\t " },
      headers: { Origin: base },
    });
    assert.equal(blank.status(), 422);
    await page.locator("textarea").fill("   ");
    assert(await sendButton(page).isDisabled(), "send enabled for a blank message");
    check("blank messages are refused (422 from the API; send disabled in the UI)");

    // --- delete a conversation ----------------------------------------------------------
    const conversations = await (await page.request.get(base + "/api/conversations?agent_id=study")).json();
    const doomed = conversations[0];
    await page.getByRole("button", { name: /Conversation history/ }).click();
    await page.getByRole("button", { name: `Delete conversation: ${doomed.title}` }).click();
    await page.getByRole("button", { name: `Delete conversation: ${doomed.title}` }).waitFor({ state: "detached" });
    assert.equal((await page.request.get(base + `/api/conversations/${doomed.id}`)).status(), 404);
    check("deleting a conversation removes it for good");

    // --- account switching ---------------------------------------------------------------
    await page.goto(base + "/memory");
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await page.waitForURL(base + "/login");
    await signIn(page, KEY_B);
    await page.goto(base + "/memory");
    await page.locator("main").waitFor();
    await page.waitForLoadState("networkidle");
    assert.equal(await page.getByText("Cairo", { exact: true }).count(), 0, "B sees A's memory");
    const bConversations = await (await page.request.get(base + "/api/conversations")).json();
    assert.deepEqual(bConversations, [], "B sees A's conversations");
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await page.waitForURL(base + "/login");
    await signIn(page, KEY_A);
    await page.goto(base + "/memory");
    await page.getByText("Cairo", { exact: true }).waitFor();
    check("switching accounts shows each person only their own memory and conversations");

    // --- a revoked session is sent to sign in, not told the reply broke -------------------
    const second = await browser.newContext({ ignoreHTTPSErrors: true });
    const elsewhere = await second.newPage();
    elsewhere.on("dialog", (d) => d.accept());
    await signIn(elsewhere, KEY_A);
    await elsewhere.goto(base + "/account");
    await page.goto(base + "/agents/study");
    await page.locator("textarea").waitFor();
    await elsewhere.getByRole("button", { name: "Sign out every device" }).click();
    await elsewhere.waitForURL(/\/login/);
    await send(page, "are you still there?");
    await page.waitForURL(/\/login/, { timeout: 15000 });
    check("a revoked session is sent to sign in");
    await second.close();
    await signIn(page, KEY_A);

    // --- an unfinished reply is spoken, not only drawn -----------------------------------
    await page.goto(base + "/agents/career");
    await send(page, "qa-truncate spoken");
    await page.getByRole("button", { name: "Continue", exact: true }).waitFor();
    const spoken = await page.evaluate(() =>
      [...document.querySelectorAll('[role="alert"], [role="status"], [aria-live]')]
        .map((el) => el.innerText.trim())
        .filter(Boolean),
    );
    assert(spoken.some((t) => t.includes("length limit")), `nothing announced: ${JSON.stringify(spoken)}`);
    check("an unfinished reply is announced to assistive technology");

    // --- a duplicate memory label is answered, not crashed -------------------------------
    const save = async (key, value) =>
      (await page.request.post(base + "/api/memory/shared", { data: { key, value }, headers: { Origin: base } })).json();
    const original = await save("alpha_label", "one");
    await save("beta_label", "two");
    const clash = await page.request.patch(base + `/api/memory/shared/${original.id}`, {
      data: { key: "beta_label" },
      headers: { Origin: base },
    });
    assert.equal(clash.status(), 409);
    const afterClash = await page.request.get(base + "/api/health/detail");
    assert.equal(afterClash.status(), 200, "a client mistake degraded readiness");
    check("a duplicate memory label is refused without paging the operator");

    // --- readiness through the proxy ---------------------------------------------------
    const ready = await page.request.get(base + "/api/health/detail");
    assert.equal(ready.status(), 200);
    const body = await ready.json();
    assert.equal(body.environment, "production");
    assert.equal(body.schema_current, true);
    check("readiness through Caddy: production, schema current");
    await context.close();

    // --- mobile ------------------------------------------------------------------------
    const phone = await session(browser, { width: 390, height: 844 });
    await signIn(phone.page, KEY_A);
    for (const route of ["/", "/team", "/memory", "/agents/study"]) {
      await phone.page.goto(base + route);
      await phone.page.waitForLoadState("networkidle");
      await phone.page.locator("main").waitFor();
      assert(
        await phone.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        `${route} overflows at 390px`,
      );
    }
    await send(phone.page, "qa-truncate on a phone");
    await lastReply(phone.page).getByText(cut).waitFor();
    await phone.page.getByRole("button", { name: "Continue", exact: true }).waitFor();
    assert(await phone.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    check("390px: no overflow, and the completion notice and recovery action fit");
    await phone.context.close();

    assert.deepEqual(results.cspViolations, [], "CSP violations");
    assert.deepEqual(results.pageErrors, [], "uncaught page errors");
    check("no CSP violations and no uncaught page errors across the run");
  } finally {
    fs.writeFileSync(report, JSON.stringify(results, null, 2));
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
