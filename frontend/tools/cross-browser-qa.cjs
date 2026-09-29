/* The same app in Chromium, Firefox and WebKit (Safari's engine): pages fit
   and really are larger at 150% text size, drawers fit and close, talk mode
   lets go of the microphone when the chat changes, and Listen stops.

   Playwright's Firefox and WebKit builds stand in for Firefox and Safari; they
   are not the shipping browsers. Run against a throwaway QA API and a
   production build (see regression-qa.cjs), with the browsers installed:
     node <playwright-core>/cli.js install firefox webkit
     PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/cross-browser-qa.cjs [chromium firefox webkit] */
const pw = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const URL = process.env.QA_URL || "http://localhost:3000";
const KEY = "q".repeat(40);
const ENGINES = process.argv.slice(2).length ? process.argv.slice(2) : ["chromium", "firefox", "webkit"];
const ROUTES = ["/", "/agents/career", "/memory", "/plans", "/account", "/cv", "/money", "/chats", "/team"];
const results = [];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function check(engine, name, ok, detail = "") {
  results.push({ engine, name, ok: !!ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} [${engine}] ${name}${detail ? " — " + detail : ""}`);
}

const INSTRUMENT = () => {
  window.__mics = [];
  window.__micDelay = 0;
  window.__plays = 0;
  const gum = navigator.mediaDevices?.getUserMedia?.bind(navigator.mediaDevices);
  if (gum) {
    navigator.mediaDevices.getUserMedia = async (c) => {
      if (window.__micDelay) await new Promise((r) => setTimeout(r, window.__micDelay));
      const s = await gum(c);
      window.__mics.push(s);
      return s;
    };
  }
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    window.__plays += 1;
    return play.call(this);
  };
};

function silenceWav() {
  const data = Buffer.alloc(16000 * 2);
  const head = Buffer.alloc(44);
  head.write("RIFF", 0); head.writeUInt32LE(36 + data.length, 4); head.write("WAVE", 8);
  head.write("fmt ", 12); head.writeUInt32LE(16, 16); head.writeUInt16LE(1, 20); head.writeUInt16LE(1, 22);
  head.writeUInt32LE(16000, 24); head.writeUInt32LE(32000, 28); head.writeUInt16LE(2, 32); head.writeUInt16LE(16, 34);
  head.write("data", 36); head.writeUInt32LE(data.length, 40);
  return Buffer.concat([head, data]);
}

async function launch(engine) {
  if (engine === "firefox") {
    return pw.firefox.launch({
      headless: true,
      firefoxUserPrefs: { "media.navigator.streams.fake": true, "media.navigator.permission.disabled": true },
    });
  }
  if (engine === "webkit") return pw.webkit.launch({ headless: true });
  return pw.chromium.launch({
    channel: "chrome",
    headless: true,
    args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"],
  });
}

async function run(engine) {
  const browser = await launch(engine);
  const context = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  if (engine !== "firefox") await context.grantPermissions(["microphone"], { origin: URL }).catch(() => undefined);
  await context.addInitScript(INSTRUMENT);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(`${page.url()}: ${e.message}`));
  let transcribeCalls = 0;
  let speakHold = 0;
  await page.route("**/api/voice", (r) => r.fulfill({ json: { transcribe: true, speak: true, max_seconds: 60 } }));
  await page.route("**/api/voice/transcribe", async (r) => {
    transcribeCalls += 1;
    await r.fulfill({ json: { text: "Remember my dentist appointment" } });
  });
  await page.route("**/api/voice/speak", async (r) => {
    await sleep(speakHold);
    await r.fulfill({ body: silenceWav(), headers: { "Content-Type": "audio/wav" } });
  });
  const sentSpeech = [];
  page.on("request", (req) => {
    if (req.url().includes("/chat/stream") && (req.postData() || "").includes("dentist")) sentSpeech.push(req.url());
  });
  const api = (p, init = {}) =>
    page.evaluate(async ([p, init]) => {
      const r = await fetch(`/api${p}`, { ...init, headers: { "Content-Type": "application/json" } });
      return { status: r.status, body: await r.json().catch(() => null) };
    }, [p, init]);

  const signInReady = page.waitForResponse((response) => response.url().endsWith("/api/auth/status") && response.ok());
  await page.goto(`${URL}/login`);
  await signInReady;
  await page.getByRole("button", { name: /invitation key/i }).click();
  await page.fill("#access-key", KEY);
  await page.getByRole("button", { name: /meet your team/i }).click();
  await page.waitForURL(`${URL}/`);

  // --- text size: pages fit, and are really larger ------------------------------------
  for (const locale of ["en", "ar"]) {
    for (const scale of [1, 1.5]) {
      await api("/users/me", { method: "PATCH", body: JSON.stringify({ locale, ui_preferences: { text_scale: scale } }) });
      await context.addCookies([{ name: "fareeq_locale", value: locale, url: URL }, { name: "fareeq_a11y", value: String(scale), url: URL }]);
      for (const [label, size] of [["desktop", { width: 1280, height: 860 }], ["phone", { width: 390, height: 844 }]]) {
        await page.setViewportSize(size);
        const bad = [];
        let header = 0;
        for (const route of ROUTES) {
          await page.goto(`${URL}${route}`);
          await page.waitForTimeout(600);
          const m = await page.evaluate(() => ({
            over: document.documentElement.scrollWidth - innerWidth,
            header: document.querySelector("header")?.getBoundingClientRect().height ?? 0,
          }));
          if (m.over > 1) bad.push(`${route} +${m.over}px`);
          if (route === "/team") header = m.header;
        }
        check(engine, `${locale} ${scale * 100}% ${label}: no page scrolls sideways`, bad.length === 0, bad.join(", "));
        // The header is 62px at 100%; at 150% it must be drawn about 1.5 times as tall.
        const expected = 62 * scale;
        check(engine, `${locale} ${scale * 100}% ${label}: text size applied`, Math.abs(header - expected) <= 6, `header ${Math.round(header)}px, expected ~${expected}px`);
      }
    }
  }

  // --- drawers at 150%, both directions, phone and desktop -------------------------------
  for (const locale of ["en", "ar"]) {
    await api("/users/me", { method: "PATCH", body: JSON.stringify({ locale, ui_preferences: { text_scale: 1.5 } }) });
    await context.addCookies([{ name: "fareeq_locale", value: locale, url: URL }, { name: "fareeq_a11y", value: "1.5", url: URL }]);
    for (const [label, size] of [["desktop", { width: 1280, height: 860 }], ["phone", { width: 390, height: 844 }]]) {
      await page.setViewportSize(size);
      for (const [name, route, button] of [
        ["template drawer", "/agents/career", locale === "ar" ? "القوالب" : "Templates"],
        ["import drawer", "/memory", locale === "ar" ? "استورد من ChatGPT أو Claude" : "Import from ChatGPT or Claude"],
      ]) {
        await page.goto(`${URL}${route}`);
        await page.waitForTimeout(700);
        await page.getByRole("button", { name: button, exact: true }).click();
        await page.locator("dialog[open]").waitFor({ timeout: 5000 });
        await sleep(400);
        const fit = await page.evaluate(() => {
          const d = document.querySelector("dialog[open]");
          const w = innerWidth, h = innerHeight;
          const inside = (x, y) => d.contains(document.elementFromPoint(x, y));
          const phone = w < 640;
          const x = phone ? w / 2 : document.documentElement.dir === "rtl" ? 20 : w - 20;
          return { top: inside(x, phone ? h * 0.15 : 4), bottom: inside(x, h - 4), over: document.documentElement.scrollWidth - w };
        });
        check(engine, `${name} ${locale} 150% ${label} fits`, fit.top && fit.bottom && fit.over <= 1, JSON.stringify(fit));
        await page.keyboard.press("Escape");
        await sleep(300);
        check(engine, `${name} ${locale} 150% ${label} closes with Escape`, (await page.locator("dialog[open]").count()) === 0);
      }
    }
  }
  await api("/users/me", { method: "PATCH", body: JSON.stringify({ locale: "en", ui_preferences: { text_scale: 1 } }) });
  await context.addCookies([{ name: "fareeq_locale", value: "en", url: URL }, { name: "fareeq_a11y", value: "1", url: URL }]);
  await page.setViewportSize({ width: 1280, height: 860 });

  // --- talk mode lets go of the microphone when the chat changes -------------------------
  await page.goto(`${URL}/agents/career`);
  await page.fill("#composer", "Hello Harvey");
  await page.keyboard.press("Enter");
  await page.locator(".assistant-message").first().waitFor({ timeout: 20000 });
  await sleep(500);
  const live = () => page.evaluate(() => window.__mics.flatMap((s) => s.getTracks()).filter((t) => t.readyState === "live").length);
  const talk = page.getByRole("region", { name: "Talking hands-free" });
  const canRecord = await page.evaluate(() => typeof MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia);
  if (!canRecord) {
    check(engine, "talk mode: this engine can record", false, "no MediaRecorder/getUserMedia");
  } else {
    const callsBefore = transcribeCalls;
    await page.getByRole("button", { name: "Talk hands-free" }).click();
    await page.waitForFunction(() => window.__mics.length > 0, null, { timeout: 8000 }).catch(() => undefined);
    await sleep(800);
    const opened = await live();
    await page.getByRole("button", { name: "Start an incognito chat" }).click();
    await page.getByRole("button", { name: "Start", exact: true }).click();
    await sleep(2500);
    check(engine, "talk mode had the microphone", opened > 0, `${opened} live tracks`);
    check(engine, "switching to incognito mid-recording closes talk mode", !(await talk.isVisible()));
    check(engine, "and releases the microphone", (await live()) === 0);
    check(engine, "and sends nothing", transcribeCalls === callsBefore && sentSpeech.length === 0);
    await page.getByRole("button", { name: "Leave incognito" }).click();
    await sleep(500);
    await page.evaluate(() => (window.__micDelay = 2000));
    const micsBefore = await page.evaluate(() => window.__mics.length);
    await page.getByRole("button", { name: "Talk hands-free" }).click();
    await sleep(300);
    await page.getByRole("button", { name: "Start an incognito chat" }).click();
    await page.getByRole("button", { name: "Start", exact: true }).click();
    await sleep(3500);
    const granted = (await page.evaluate(() => window.__mics.length)) - micsBefore;
    check(engine, "a microphone granted after the switch is released at once", (await live()) === 0, `${granted} granted late`);
    await page.getByRole("button", { name: "Leave incognito" }).click();
    await page.evaluate(() => (window.__micDelay = 0));
  }

  // --- Listen stops while the voice is still coming --------------------------------------
  const convos = (await api("/conversations?agent_id=career")).body;
  await page.goto(`${URL}/agents/career?c=${convos[0].id}`);
  await page.locator(".assistant-message").first().waitFor({ timeout: 10000 });
  speakHold = 2000;
  await page.evaluate(() => (window.__plays = 0));
  await page.getByRole("button", { name: "Listen" }).first().click();
  await sleep(300);
  await page.getByRole("button", { name: "Stop" }).first().click();
  await sleep(3000);
  check(engine, "Stop before the voice arrives: nothing plays", (await page.evaluate(() => window.__plays)) === 0);
  speakHold = 0;

  check(engine, "no page errors", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
}

(async () => {
  for (const engine of ENGINES) {
    try {
      await run(engine);
    } catch (e) {
      check(engine, "run completed", false, e.message.split("\n")[0]);
    }
  }
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} passed`);
  process.exit(failed ? 1 : 0);
})();
