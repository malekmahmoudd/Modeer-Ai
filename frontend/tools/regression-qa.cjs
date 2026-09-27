/* Whole-app regression in a real browser, English and Arabic.

   Run against a throwaway QA API and a production build:
     cd backend && .venv/bin/python -m tools.qa_server --reset --port 8000 --db ui-qa.db
     cd frontend && npx next build && npx next start -p 3000
     PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/regression-qa.cjs
   QA_URL overrides the address; QA_SHOTS saves screenshots to that folder.
   The mock model answers; nothing reaches a real provider. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const URL = process.env.QA_URL || "http://localhost:3000";
const SHOTS = process.env.QA_SHOTS || "";
const KEY = "q".repeat(40);
const PASSWORD = "a long enough password 42";
const results = [];
const pageErrors = [];

function check(name, ok, detail = "") {
  results.push({ name, ok: !!ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}
async function shot(page, name) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
}
async function overflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}
async function waitReply(page, count) {
  await page.waitForFunction(
    (n) => document.querySelectorAll(".assistant-message").length >= n && !document.querySelector(".caret"),
    count,
    { timeout: 20000 },
  );
  await page.waitForTimeout(400);
}
function totp(secret) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const ch of secret.replace(/\s|=/g, "").toUpperCase()) bits += alphabet.indexOf(ch).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const mac = crypto.createHmac("sha1", key).update(msg).digest();
  const o = mac[mac.length - 1] & 15;
  return String((mac.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, "0");
}
async function signIn(page) {
  await page.goto(`${URL}/login`);
  await page.getByRole("button", { name: /invitation key/i }).click();
  await page.fill("#access-key", KEY);
  await page.getByRole("button", { name: /meet your team/i }).click();
  await page.waitForURL(`${URL}/`);
}

(async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
  });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: URL });
  const page = await context.newPage();
  page.on("pageerror", (e) => pageErrors.push(`${page.url()}: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && pageErrors.push(`console: ${m.text()}`));

  // --- home, brand, installable ------------------------------------------------------
  await signIn(page);
  check("wordmark reads Fareeq AI", (await page.locator(".wordmark").first().textContent()) === "Fareeq AI");
  check("line under Leo", (await page.locator(".sunshine-subtitle").textContent()) === "Knows you. Knows who can help.");
  const manifest = await page.request.get(`${URL}/manifest.webmanifest`);
  check("manifest served", manifest.ok() && (await manifest.json()).short_name === "Fareeq AI");
  await page.getByRole("button", { name: /My Front Desk/ }).click();
  check("front desk opens its chooser", await page.getByRole("button", { name: /Pin|Unpin/ }).first().isVisible());
  await page.keyboard.press("Escape");
  await shot(page, "en-home");

  // --- chat: actions, regenerate, edit, save, reading desk --------------------------------
  await page.goto(`${URL}/agents/study`);
  await page.fill("#composer", "Help me revise thermodynamics for Friday");
  await page.keyboard.press("Enter");
  await waitReply(page, 1);
  const actions = page.getByRole("group", { name: "Reply actions" }).last();
  await actions.getByRole("button", { name: "Copy" }).click();
  check("copy works", (await page.evaluate(() => navigator.clipboard.readText())).length > 20);
  const before = await page.locator(".assistant-message").count();
  await actions.getByRole("button", { name: "Regenerate" }).click();
  await waitReply(page, before);
  check("regenerate replaces the reply", (await page.locator(".assistant-message").count()) === before);
  await page.getByRole("button", { name: "Edit your last message" }).click();
  await page.waitForTimeout(400);
  check("edit returns the message", (await page.inputValue("#composer")).includes("thermodynamics"));
  await page.fill("#composer", "Help me revise entropy for Friday");
  await page.keyboard.press("Enter");
  await waitReply(page, 1);
  await page.getByRole("group", { name: "Reply actions" }).last().getByRole("button", { name: "Save this reply" }).click();
  await page.waitForTimeout(400);
  check("save pins the reply", (await (await page.request.get(`${URL}/api/conversations/pinned`)).json()).length === 1);
  const reading = page.getByRole("button", { name: /Reading Desk/ });
  check("reading desk is offered", (await reading.count()) > 0);
  await shot(page, "en-chat");

  // --- drafts and offline ----------------------------------------------------------------
  await page.fill("#composer", "half-written thought about heat engines");
  await page.waitForTimeout(300);
  await page.reload();
  await page.waitForSelector("#composer");
  await page.waitForTimeout(800);
  check("draft survives a reload", (await page.inputValue("#composer")).includes("heat engines"));
  await page.fill("#composer", "");
  const replies = await page.locator(".assistant-message").count();
  await context.setOffline(true);
  await page.fill("#composer", "Sent while offline");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(500);
  check("offline message waits", await page.getByText("Waiting for the connection…").isVisible());
  await context.setOffline(false);
  await waitReply(page, replies + 1);
  check("sent when back online", !(await page.getByText("Waiting for the connection…").isVisible()));

  // --- search, teammate handoff, incognito -----------------------------------------------
  await page.goto(`${URL}/`);
  await page.keyboard.press("Control+k");
  await page.fill("#search-input", "entropy");
  await page.waitForSelector("[role=dialog] ul li button", { timeout: 5000 });
  await page.locator("[role=dialog] ul li button").first().click();
  await page.waitForURL(/\/agents\/study\?c=/);
  check("search opens the chat", true);
  await page.waitForTimeout(800);
  await page.getByRole("button", { name: "Ask a teammate" }).last().click();
  await page.getByRole("menuitem", { name: /Ask Harvey/ }).click();
  await page.waitForURL(/\/agents\/career/);
  await page.waitForTimeout(900);
  check("teammate gets the quote", (await page.inputValue("#composer")).startsWith("About this, from Nova"));
  await page.fill("#composer", "");
  const listed = (await (await page.request.get(`${URL}/api/conversations`)).json()).length;
  await page.getByRole("button", { name: "Start an incognito chat" }).click();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await page.fill("#composer", "I am thinking about quitting my job");
  await page.keyboard.press("Enter");
  await waitReply(page, 1);
  check("incognito stays out of lists", (await (await page.request.get(`${URL}/api/conversations`)).json()).length === listed);
  await page.getByRole("button", { name: "Leave incognito" }).click();

  // --- plans, week, team -----------------------------------------------------------------
  await page.goto(`${URL}/plans`);
  await page.getByRole("link", { name: "Open the chat" }).first().waitFor({ timeout: 6000 }).catch(() => undefined);
  check("saved reply on Plans", (await page.getByRole("link", { name: "Open the chat" }).count()) >= 1);
  await page.goto(`${URL}/week`);
  check("week page", await page.getByRole("heading", { name: "The week in review." }).isVisible());
  await page.goto(`${URL}/team`);
  await page.fill("#team-question", "Should I take a data bootcamp?");
  for (const name of ["Nova", "Harvey"]) await page.getByRole("button", { name, exact: true }).click();
  await page.getByRole("button", { name: "Ask the team" }).click();
  await page.getByText("Leo brings it together").waitFor({ timeout: 30000 });
  check("ask my team answers", (await page.locator("details").count()) === 2);
  check("team comparison is offered", await page.getByText(/Team Comparison/).first().isVisible());

  // --- account: usage, devices, two-step ------------------------------------------------
  await page.request.patch(`${URL}/api/users/me`, { data: { email: "qa@example.com" }, headers: { Origin: URL } });
  await page.goto(`${URL}/account`);
  await page.getByText(/% used today/).first().waitFor({ timeout: 6000 });
  check("usage percentage", true);
  await page.fill("#new-password", PASSWORD);
  await page.getByRole("button", { name: "Set password" }).click();
  await page.getByLabel("I've saved these codes").check();
  await page.getByRole("button", { name: "Done" }).click();
  await page.fill("#twostep-password", PASSWORD);
  await page.getByRole("button", { name: "Set up two-step sign-in" }).click();
  const secret = (await page.locator("p.font-mono").first().textContent()).replace(/\s/g, "");
  await page.fill("#twostep-code", totp(secret));
  await page.getByRole("button", { name: "Turn on" }).click();
  await page.getByText("Two-step sign-in is on.").first().waitFor({ timeout: 5000 });
  check("two-step turns on", true);
  check("this device listed", await page.getByText("This device", { exact: true }).isVisible());
  await shot(page, "en-account");

  // --- settings: text size, contrast, dialect, hidden teammates ----------------------------
  await page.getByRole("radio", { name: "130%" }).check();
  await page.waitForTimeout(400);
  check("text size applies", (await page.evaluate(() => document.documentElement.style.getPropertyValue("--text-scale"))) === "1.3");
  await page.reload();
  check("text size survives a reload", (await page.evaluate(() => document.documentElement.style.getPropertyValue("--text-scale"))) === "1.3");
  await page.getByRole("radio", { name: "100%" }).check();
  await page.getByLabel("High contrast").check();
  await page.waitForTimeout(300);
  check("high contrast applies", await page.evaluate(() => document.documentElement.classList.contains("high-contrast")));
  await page.getByLabel("High contrast").uncheck();
  await page.getByRole("radio", { name: "Egyptian" }).check();
  await page.waitForTimeout(400);
  check("dialect saved", (await (await page.request.get(`${URL}/api/users/me`)).json()).reply_dialect === "egyptian");
  await page.getByRole("checkbox", { name: "Tessa", exact: true }).uncheck();
  await page.waitForTimeout(400);
  check("hiding saved", ((await (await page.request.get(`${URL}/api/users/me`)).json()).ui_preferences.hidden_agents || []).includes("travel"));
  await page.goto(`${URL}/team`);
  const showHidden = page.getByRole("button", { name: /Show hidden teammates/ });
  await showHidden.waitFor({ timeout: 6000 }).catch(() => undefined);
  check("hidden teammate left off Team", await showHidden.isVisible());
  await page.goto(`${URL}/account`);
  await page.getByRole("checkbox", { name: "Tessa", exact: true }).check();
  await page.waitForTimeout(400);

  // --- tools: templates, all chats, talk mode, quick note, import, CV, money ---------------
  await page.goto(`${URL}/agents/career`);
  await page.getByRole("button", { name: "Templates" }).click();
  await page.getByRole("button", { name: /Sharpen a CV bullet/ }).click();
  await page.getByRole("textbox", { name: "role", exact: true }).fill("analyst");
  await page.getByRole("textbox", { name: "bullet", exact: true }).fill("Made weekly reports");
  await page.getByRole("button", { name: "Put it in the message box" }).click();
  check("template fills the message box", (await page.inputValue("#composer")).includes("for a analyst role"));
  await page.fill("#composer", "");
  await page.getByRole("button", { name: "Talk hands-free" }).click();
  check("talk mode opens", await page.getByRole("region", { name: "Talking hands-free" }).isVisible());
  await page.getByRole("button", { name: "End talking" }).first().click();
  check("talk mode closes", !(await page.getByRole("region", { name: "Talking hands-free" }).isVisible()));
  await page.goto(`${URL}/chats`);
  await page.getByRole("button", { name: /^Pin / }).first().click();
  await page.waitForTimeout(400);
  const chats = await (await page.request.get(`${URL}/api/conversations`)).json();
  check("pinning a chat puts it first", Boolean(chats[0]?.pinned_at));
  // The quick note and the import each ask the model; wait out the account's
  // six-a-minute limit (production's) rather than raising it for the test.
  await page.waitForTimeout(61000);
  await page.goto(`${URL}/plans`);
  await page.fill("#capture-text", "Ran 5 km this morning");
  await page.getByRole("button", { name: "Find what to keep" }).click();
  await page.waitForFunction(() => /Keep these\?|Nothing to log|[.!]$/.test(document.querySelector('section[aria-labelledby="capture-title"] [role=status], section[aria-labelledby="capture-title"] [role=alert], section[aria-labelledby="capture-title"] .font-bold')?.textContent || ""), null, { timeout: 15000 }).catch(() => undefined);
  const captureText = (await page.locator('section[aria-labelledby="capture-title"] [role=status], section[aria-labelledby="capture-title"] [role=alert]').allTextContents()).join(" | ") + (await page.getByText("Keep these?").count() ? " Keep these?" : "");
  check("quick note is read, nothing saved yet", /Keep these\?|Nothing to log/.test(captureText), captureText.slice(0, 80));
  await page.goto(`${URL}/memory`);
  await page.getByRole("button", { name: "Import from ChatGPT or Claude" }).click();
  await page.fill("#import-text", "I work as a data analyst in Cairo and I prefer short answers.");
  await page.getByRole("button", { name: "Find facts about me" }).click();
  await page.waitForFunction(() => {
    const d = document.querySelector("dialog[open]");
    return d && (/Tick what Leo|No facts about you/.test(d.textContent) || d.querySelector("[role=alert]"));
  }, null, { timeout: 15000 }).catch(() => undefined);
  const importText = (await page.locator("dialog[open]").textContent()) || "";
  check("import previews facts", /Tick what Leo|No facts about you/.test(importText), importText.slice(-80));
  await page.goto(`${URL}/cv`);
  await page.getByRole("button", { name: "Start a CV" }).click();
  await page.getByLabel("Your name").fill("Sara Ali");
  await page.getByRole("button", { name: "Add a role" }).click();
  await page.getByLabel(/What you achieved/).fill("Responsible for reports");
  check("bullet check speaks up", await page.getByText(/start with what you did/).isVisible());
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByText("CV saved.").waitFor({ timeout: 5000 });
  const cvs = await (await page.request.get(`${URL}/api/cv`)).json();
  const docx = await page.request.get(`${URL}/api/cv/${cvs[0].id}/docx`);
  check("CV downloads as Word", docx.ok() && (await docx.body()).subarray(0, 2).toString() === "PK");
  await page.goto(`${URL}/money`);
  await page.getByLabel("Cash and savings").fill("500000");
  await page.getByLabel(/Price of 1 g/).fill("4000");
  check("zakat is worked out", await page.getByText(/Zakat due: EGP/).isVisible());

  // --- Arabic: interface, server text, dates, layout ---------------------------------------
  await page.getByRole("button", { name: "Switch the interface to Arabic" }).click();
  await page.waitForTimeout(500);
  check("switches to Arabic", (await page.getAttribute("html", "dir")) === "rtl");
  const error = await page.request.delete(`${URL}/api/goals/nope`, { headers: { Origin: URL } });
  check("errors in Arabic", (await error.json()).detail === "لم يُعثر على الهدف");
  await page.request.post(`${URL}/api/goals`, { data: { title: "Pass the thermodynamics final" }, headers: { Origin: URL } });
  const briefing = await (await page.request.get(`${URL}/api/briefings/today?refresh=true`)).json();
  check("briefing written in Arabic", /أولوياتك|لا أعرف/.test(briefing.summary), briefing.summary.slice(0, 40));
  await page.goto(`${URL}/agents/modeer`);
  await page.fill("#composer", "عندي مقابلة الخميس الجاي");
  await page.keyboard.press("Enter");
  await waitReply(page, 1);
  check("Arabic chat round trip", (await page.locator(".assistant-message").count()) >= 1);
  await page.goto(`${URL}/`);
  await page.waitForTimeout(800);
  const heroAlt = (await page.locator("img.sunshine-hero-art").getAttribute("alt")) || "";
  check("Arabic artwork description", heroAlt.includes("ليو"), heroAlt.slice(0, 30));
  for (const [label, w, h] of [["desktop", 1440, 900], ["mobile", 390, 844]]) {
    await page.setViewportSize({ width: w, height: h });
    for (const route of ["/", "/team", "/agents/study", "/plans", "/week", "/memory", "/goals", "/account", "/chats", "/cv", "/money"]) {
      await page.goto(`${URL}${route}`);
      await page.waitForTimeout(700);
      const over = await overflow(page);
      check(`ar ${label} ${route} fits`, over <= 1, `overflow ${over}px`);
    }
  }
  await shot(page, "ar-account-mobile");
  await page.request.patch(`${URL}/api/users/me`, { data: { locale: "en" }, headers: { Origin: URL } });

  check("no page errors", pageErrors.length === 0, pageErrors.slice(0, 4).join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  if (SHOTS) fs.writeFileSync(path.join(SHOTS, "results.json"), JSON.stringify({ results, pageErrors }, null, 2));
  console.log(`\n${results.length - failed}/${results.length} passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error("QA crashed:", e.message);
  process.exit(2);
});
