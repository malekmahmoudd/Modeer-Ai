/* Browser checks for the review fixes of the twelve-feature batch: talk mode
   never sends to another chat, reading aloud stops when asked, a quick note
   saves once, a CV copy never loses edits, imports never send an assistant's
   replies, and drawers fit the screen at every text size.

   Run against a throwaway QA API and a production build (the mock model; the
   voice endpoints are answered by this script, nothing reaches a provider):
     cd backend && .venv/bin/python -m tools.qa_server --reset --port 8000 --db ui-qa.db
     cd frontend && npx next build && npx next start -p 3000
     PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/review-fixes-qa.cjs
   Talk mode uses Chrome's fake microphone fed from a generated WAV: silence, a
   tone the voice detector hears as speech, then silence. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const URL = process.env.QA_URL || "http://localhost:3000";
const KEY = "q".repeat(40);
const results = [];
const pageErrors = [];

function check(name, ok, detail = "") {
  results.push({ name, ok: !!ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 16 kHz mono WAV: 1 s silence, 1.2 s of a 440 Hz tone, 6 s silence. */
function speechWav() {
  const rate = 16000;
  const samples = [];
  const push = (n, f) => { for (let i = 0; i < n; i++) samples.push(f(i)); };
  push(rate, () => 0);
  push(rate * 1.2, (i) => Math.round(Math.sin((2 * Math.PI * 440 * i) / rate) * 12000));
  push(rate * 6, () => 0);
  const data = Buffer.alloc(samples.length * 2);
  samples.forEach((s, i) => data.writeInt16LE(s, i * 2));
  const head = Buffer.alloc(44);
  head.write("RIFF", 0); head.writeUInt32LE(36 + data.length, 4); head.write("WAVE", 8);
  head.write("fmt ", 12); head.writeUInt32LE(16, 16); head.writeUInt16LE(1, 20); head.writeUInt16LE(1, 22);
  head.writeUInt32LE(rate, 24); head.writeUInt32LE(rate * 2, 28); head.writeUInt16LE(2, 32); head.writeUInt16LE(16, 34);
  head.write("data", 36); head.writeUInt32LE(data.length, 40);
  const file = path.join(os.tmpdir(), "fareeq-qa-speech.wav");
  fs.writeFileSync(file, Buffer.concat([head, data]));
  return file;
}

// Counts microphones and playback, and can hold the microphone permission.
const INSTRUMENT = () => {
  window.__mics = [];
  window.__micDelay = 0;
  window.__plays = 0;
  window.__synth = 0;
  window.__revoked = 0;
  const gum = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
  navigator.mediaDevices.getUserMedia = async (c) => {
    if (window.__micDelay) await new Promise((r) => setTimeout(r, window.__micDelay));
    const s = await gum(c);
    window.__mics.push(s);
    return s;
  };
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    window.__plays += 1;
    const started = play.call(this);
    // Starting playback takes a moment on a real device: widen that window.
    return started.then(() => new Promise((r) => setTimeout(r, window.__playDelay || 0)));
  };
  const speak = speechSynthesis.speak.bind(speechSynthesis);
  speechSynthesis.speak = (u) => { window.__synth += 1; return speak(u); };
  const revoke = URL.revokeObjectURL.bind(URL);
  URL.revokeObjectURL = (u) => { window.__revoked += 1; return revoke(u); };
};
const micsLive = (page) =>
  page.evaluate(() => window.__mics.flatMap((s) => s.getTracks()).filter((t) => t.readyState === "live").length);

/** A second of silence as a WAV, for the natural-voice endpoint. */
function silenceWav() {
  const data = Buffer.alloc(16000 * 2);
  const head = Buffer.alloc(44);
  head.write("RIFF", 0); head.writeUInt32LE(36 + data.length, 4); head.write("WAVE", 8);
  head.write("fmt ", 12); head.writeUInt32LE(16, 16); head.writeUInt16LE(1, 20); head.writeUInt16LE(1, 22);
  head.writeUInt32LE(16000, 24); head.writeUInt32LE(32000, 28); head.writeUInt16LE(2, 32); head.writeUInt16LE(16, 34);
  head.write("data", 36); head.writeUInt32LE(data.length, 40);
  return Buffer.concat([head, data]);
}

async function signIn(page) {
  const ready = page.waitForResponse((response) => response.url().endsWith("/api/auth/status") && response.ok());
  await page.goto(`${URL}/login`);
  await ready;
  await page.getByRole("button", { name: /invitation key/i }).click();
  await page.fill("#access-key", KEY);
  await page.getByRole("button", { name: /meet your team/i }).click();
  await page.waitForURL(`${URL}/`);
}
const api = (page, p, init = {}) =>
  page.evaluate(async ([p, init]) => {
    const r = await fetch(`/api${p}`, { ...init, headers: { "Content-Type": "application/json" } });
    return { status: r.status, body: await r.json().catch(() => null) };
  }, [p, init]);

(async () => {
  const wav = speechWav();
  const browser = await chromium.launch({
    channel: "chrome",
    headless: true,
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      `--use-file-for-fake-audio-capture=${wav}`,
      "--autoplay-policy=no-user-gesture-required",
    ],
  });
  const context = await browser.newContext({ viewport: { width: 1280, height: 860 } });
  await context.grantPermissions(["microphone"], { origin: URL });
  await context.addInitScript(INSTRUMENT);
  const page = await context.newPage();
  page.on("pageerror", (e) => pageErrors.push(`${page.url()}: ${e.message}`));

  // Voice endpoints answered here: dictation available, natural voices on,
  // transcription and speech held as long as each test needs.
  let transcribeHold = 0;
  let transcribeCalls = 0;
  let speakHold = 0;
  let speakCalls = 0;
  await page.route("**/api/voice", (r) => r.fulfill({ json: { transcribe: true, speak: true, max_seconds: 60 } }));
  await page.route("**/api/voice/transcribe", async (r) => {
    transcribeCalls += 1;
    await sleep(transcribeHold);
    await r.fulfill({ json: { text: "Remember my dentist appointment" } });
  });
  await page.route("**/api/voice/speak", async (r) => {
    speakCalls += 1;
    await sleep(speakHold);
    await r.fulfill({ body: silenceWav(), headers: { "Content-Type": "audio/wav" } });
  });
  const sentSpeech = [];
  page.on("request", (req) => {
    if (req.url().includes("/chat/stream") && (req.postData() || "").includes("dentist")) sentSpeech.push(req.url());
  });

  await signIn(page);

  // --- 1. talk mode: speech never goes to another chat or privacy mode -----------------
  await page.goto(`${URL}/agents/career`);
  let releaseReply;
  const replyGate = new Promise((resolve) => { releaseReply = resolve; });
  await page.route("**/api/agents/career/chat/stream", async (route) => {
    await replyGate;
    await route.continue();
  }, { times: 1 });
  await page.fill("#composer", "Hello Harvey");
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Talk hands-free", exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelector('[aria-label="Talk hands-free"]')?.disabled);
  check("talk mode cannot start while a reply is pending", await page.getByRole("button", { name: "Talk hands-free", exact: true }).isDisabled());
  releaseReply();
  await page.locator(".assistant-message").first().waitFor({ timeout: 20000 });
  await sleep(600);
  const talk = page.getByRole("region", { name: "Talking hands-free" });

  // Positive control: nothing switched, so what was heard is sent, spoken.
  // Existing history can already contain two replies. Wait for this turn's
  // request, not a total message count that can pass before recording starts.
  const spokenRequest = page.waitForRequest(
    (req) => req.url().includes("/chat/stream") && (req.postData() || "").includes("dentist"),
    { timeout: 25000 },
  ).catch(() => null);
  await page.getByRole("button", { name: "Talk hands-free" }).click();
  await spokenRequest;
  check("talk mode sends what it heard when nothing changed", sentSpeech.length === 1, `sent ${sentSpeech.length}`);
  await page.getByRole("button", { name: "End talking" }).first().click();
  await sleep(500);
  check("ending talk mode releases the microphone", (await micsLive(page)) === 0);
  sentSpeech.length = 0;

  // a) the microphone permission is still pending when incognito starts
  await page.evaluate(() => (window.__micDelay = 2500));
  await page.getByRole("button", { name: "Talk hands-free" }).click();
  await sleep(300);
  await page.getByRole("button", { name: "Start an incognito chat" }).click();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await sleep(4000);
  check("switching during the mic prompt closes talk mode", !(await talk.isVisible()));
  check("a mic granted after the switch is released at once", (await micsLive(page)) === 0);
  await page.getByRole("button", { name: "Leave incognito" }).click();
  await page.evaluate(() => (window.__micDelay = 0));
  await sleep(500);

  // b) mid-recording, another chat is opened
  const callsBefore = transcribeCalls;
  await page.getByRole("button", { name: "Talk hands-free" }).click();
  await page.getByText("Hearing you. Pause when you're done.").waitFor({ timeout: 8000 });
  await page.getByRole("button", { name: "Start a new conversation" }).click();
  await sleep(4000);
  check("switching mid-recording closes talk mode", !(await talk.isVisible()));
  check("the recording is dropped, not written out", transcribeCalls === callsBefore, `${transcribeCalls - callsBefore} calls`);
  check("mic released after switching mid-recording", (await micsLive(page)) === 0);

  // c) transcription is in flight when incognito starts
  transcribeHold = 3500;
  const convos = (await api(page, "/conversations?agent_id=career")).body;
  await page.goto(`${URL}/agents/career?c=${convos[0].id}`);
  await sleep(800);
  const inflight = transcribeCalls;
  await page.getByRole("button", { name: "Talk hands-free" }).click();
  while (transcribeCalls === inflight) await sleep(100);
  await page.getByRole("button", { name: "Start an incognito chat" }).click();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await sleep(5000);
  check("switching during transcription sends nothing anywhere", sentSpeech.length === 0, sentSpeech.join(", "));
  check("talk mode closed after the switch", !(await talk.isVisible()));
  check("mic released after switching during transcription", (await micsLive(page)) === 0);
  await page.getByRole("button", { name: "Leave incognito" }).click();
  transcribeHold = 0;

  // --- 7. reading aloud stops at every stage ---------------------------------------------
  await page.goto(`${URL}/agents/career?c=${convos[0].id}`);
  await page.locator(".assistant-message").first().waitFor({ timeout: 10000 });
  const listen = page.getByRole("button", { name: "Listen" }).first();
  const reset = () => page.evaluate(() => { window.__plays = 0; window.__synth = 0; window.__revoked = 0; });

  // a) during the voice fetch
  speakHold = 2500;
  await reset();
  await listen.click();
  await sleep(300);
  await page.getByRole("button", { name: "Stop" }).first().click();
  await sleep(3500);
  let counts = await page.evaluate(() => ({ plays: window.__plays, synth: window.__synth }));
  check("Stop during the voice fetch: nothing plays, no device fallback", counts.plays === 0 && counts.synth === 0, JSON.stringify(counts));

  // b) leaving the chat during the fetch
  await reset();
  await listen.click();
  await sleep(300);
  await page.getByRole("link", { name: "Plans" }).first().click();
  await sleep(3500);
  counts = await page.evaluate(() => ({ plays: window.__plays, synth: window.__synth }));
  check("leaving during the voice fetch: nothing plays later", counts.plays === 0 && counts.synth === 0, JSON.stringify(counts));

  // c) while playback is starting
  speakHold = 0;
  await page.goto(`${URL}/agents/career?c=${convos[0].id}`);
  await page.locator(".assistant-message").first().waitFor({ timeout: 10000 });
  await page.evaluate(() => (window.__playDelay = 1500));
  await reset();
  await page.getByRole("button", { name: "Listen" }).first().click();
  await page.waitForFunction(() => window.__plays > 0, null, { timeout: 5000 });
  await page.getByRole("button", { name: "Stop" }).first().click();
  await sleep(2500);
  counts = await page.evaluate(() => ({
    synth: window.__synth,
    revoked: window.__revoked,
    playing: [...document.querySelectorAll("audio")].some((a) => !a.paused),
  }));
  check("Stop while playback starts: audio released, no device fallback", counts.synth === 0 && counts.revoked >= 1 && !counts.playing, JSON.stringify(counts));
  check("the Listen button is ready again", await page.getByRole("button", { name: "Listen" }).first().isVisible());
  await page.evaluate(() => (window.__playDelay = 0));

  // d) a fresh page: Stop while the voice status is still being asked
  await page.route("**/api/voice", async (r) => { await sleep(2000); await r.fulfill({ json: { transcribe: true, speak: true, max_seconds: 60 } }); });
  await page.goto(`${URL}/agents/career?c=${convos[0].id}`);
  await page.locator(".assistant-message").first().waitFor({ timeout: 10000 });
  const speaksBefore = speakCalls;
  await reset();
  await page.getByRole("button", { name: "Listen" }).first().click();
  await sleep(200);
  await page.getByRole("button", { name: "Stop" }).first().click();
  await sleep(3000);
  counts = await page.evaluate(() => ({ plays: window.__plays, synth: window.__synth }));
  check("Stop during the status lookup: no request, nothing plays", speakCalls === speaksBefore && counts.plays === 0 && counts.synth === 0, JSON.stringify({ ...counts, speak: speakCalls - speaksBefore }));
  await page.unroute("**/api/voice");
  await page.route("**/api/voice", (r) => r.fulfill({ json: { transcribe: true, speak: true, max_seconds: 60 } }));

  // --- 5. a quick note saves once ------------------------------------------------------------
  const due = new Date(Date.now() + 4 * 864e5).toISOString().slice(0, 10);
  const proposal = (agent) => ({
    checkins: [{ agent_id: "fitness", text: "Swam 1 km", amount: 1, unit: "km", details: null }],
    followups: [{ agent_id: agent, title: "Dentist check", due_on: due, ends_on: null }],
    held_back: 0,
  });
  let next = proposal("career");
  await page.route("**/api/capture", (r) => r.fulfill({ json: next }));
  let lose = true;
  await page.route("**/api/capture/save", async (r) => {
    if (lose) {
      lose = false;
      await r.fetch(); // the server saves it...
      return r.abort("connectionreset"); // ...and the answer never arrives
    }
    return r.continue();
  });
  await page.goto(`${URL}/plans`);
  await page.fill("#capture-text", "Swam 1 km, dentist on Thursday");
  await page.getByRole("button", { name: "Find what to keep" }).click();
  await page.getByText("Keep these?").waitFor({ timeout: 8000 });
  await page.getByRole("button", { name: "Save the ticked ones" }).click();
  await sleep(1200);
  check("a lost answer locks the ticks for the retry", await page.locator('section[aria-labelledby="capture-title"] input[type=checkbox]').first().isDisabled());
  await page.getByRole("button", { name: "Try again" }).click();
  await page.getByText(/Saved 2 items/).waitFor({ timeout: 8000 });
  const swims = (await api(page, "/checkins")).body.filter((c) => c.text === "Swam 1 km").length;
  const dentists = (await api(page, "/followups?status=pending")).body.filter((f) => f.title === "Dentist check").length;
  check("the retry after a lost answer saved nothing twice", swims === 1 && dentists === 1, `check-ins ${swims}, follow-ups ${dentists}`);

  // The key outlives Cancel + Find again, and a reload.
  const saveKeys = [];
  page.on("request", (req) => req.url().endsWith("/api/capture/save") && saveKeys.push(JSON.parse(req.postData() || "{}").key));
  for (const [label, detour] of [
    ["Cancel and Find again", async () => {
      await page.getByRole("button", { name: "Cancel" }).click();
    }],
    ["a reload", async () => {
      await page.reload();
      await page.fill("#capture-text", "again");
    }],
  ]) {
    next = proposal("career");
    next.checkins[0].text = `Cycled ${label}`;
    saveKeys.length = 0;
    lose = true;
    await page.fill("#capture-text", "Cycled today");
    await page.getByRole("button", { name: "Find what to keep" }).click();
    await page.getByText("Keep these?").waitFor({ timeout: 8000 });
    await page.getByRole("button", { name: "Save the ticked ones" }).click();
    await sleep(1200);
    await detour();
    await page.getByRole("button", { name: "Find what to keep" }).click();
    await page.getByText("Keep these?").waitFor({ timeout: 8000 });
    await page.getByRole("button", { name: "Save the ticked ones" }).click();
    await page.getByText(/Saved 2 items/).waitFor({ timeout: 8000 });
    const cycled = (await api(page, "/checkins")).body.filter((c) => c.text === `Cycled ${label}`).length;
    check(`retry after ${label} reuses the key`, saveKeys.length === 2 && saveKeys[0] === saveKeys[1], saveKeys.join(" / "));
    check(`retry after ${label} saves nothing twice`, cycled === 1, `${cycled}`);
  }
  // The same items saved again later, on purpose, are a new note.
  saveKeys.length = 0;
  await page.fill("#capture-text", "Cycled today");
  await page.getByRole("button", { name: "Find what to keep" }).click();
  await page.getByText("Keep these?").waitFor({ timeout: 8000 });
  await page.getByRole("button", { name: "Save the ticked ones" }).click();
  await page.getByText(/Saved \d item/).waitFor({ timeout: 8000 });
  const lastKeys = await page.evaluate(() => sessionStorage.getItem("fareeq.captureKeys"));
  check("a confirmed save forgets its key", lastKeys === null, String(lastKeys));
  check("stored keys hold no words from the note", !(await page.evaluate(() => JSON.stringify(sessionStorage))).includes("Cycled"));

  // A refused item saves nothing; the ticks unlock; the corrected save goes once.
  next = proposal("nobody");
  next.checkins[0].text = "Rowed 2 km";
  next.followups[0].title = "Bad agent thing";
  await page.fill("#capture-text", "Rowed 2 km");
  await page.getByRole("button", { name: "Find what to keep" }).click();
  await page.getByText("Keep these?").waitFor({ timeout: 8000 });
  await page.getByRole("button", { name: "Save the ticked ones" }).click();
  await sleep(1200);
  const rowsAfterRefusal = (await api(page, "/checkins")).body.filter((c) => c.text === "Rowed 2 km").length;
  check("one refused item saves nothing", rowsAfterRefusal === 0);
  await page.getByLabel(/Bad agent thing/).uncheck();
  await page.getByRole("button", { name: "Save the ticked ones" }).click();
  await page.getByText(/Saved 1 item/).waitFor({ timeout: 8000 });
  const rows = (await api(page, "/checkins")).body.filter((c) => c.text === "Rowed 2 km").length;
  check("after unticking the bad item, the rest saves once", rows === 1, `${rows}`);

  // --- 4. a CV copy never loses edits --------------------------------------------------------
  await page.goto(`${URL}/cv`);
  await page.getByRole("button", { name: "Start a CV" }).click();
  await page.getByLabel("Your name").fill("Edited Name");
  let copyCalls = 0;
  page.on("request", (req) => req.url().includes("/copy") && req.method() === "POST" && (copyCalls += 1));
  await page.route("**/api/cv/*", (r) => (r.request().method() === "PUT" ? r.fulfill({ status: 500, json: { detail: "Save failed on purpose" } }) : r.continue()));
  page.once("dialog", (d) => d.accept("Analyst"));
  await page.getByRole("button", { name: "Copy for another role" }).click();
  await page.getByText("Save failed on purpose").waitFor({ timeout: 5000 });
  check("a failed save stops the copy", copyCalls === 0);
  check("the unsaved edits stay in the form", (await page.getByLabel("Your name").inputValue()) === "Edited Name");
  await page.unroute("**/api/cv/*");
  page.once("dialog", (d) => d.accept("Analyst"));
  await page.getByRole("button", { name: "Copy for another role" }).click();
  await page.getByText("Copied. Now tailor it to the role.").waitFor({ timeout: 5000 });
  const cvs = (await api(page, "/cv")).body;
  check("after a good save the copy carries the edits", cvs.length === 2 && cvs.every((c) => c.data.name === "Edited Name"), cvs.map((c) => c.data.name).join(", "));

  // --- 3. imports never send an assistant's replies -------------------------------------------
  const previews = [];
  page.on("request", (req) => req.url().includes("/memory/import/preview") && previews.push(req.postData() || ""));
  const SECRET = "ASSISTANT-REPLY-MUST-NOT-LEAVE";
  const exportJson = JSON.stringify([
    { mapping: {
      a: { message: { author: { role: "user" }, content: { parts: ["I work as a pharmacist in Giza"] } } },
      b: { message: { author: { role: "assistant" }, content: { parts: [SECRET] } } },
    } },
  ]);
  await page.goto(`${URL}/memory`);
  await page.getByRole("button", { name: "Import from ChatGPT or Claude" }).click();
  const dialog = page.locator("dialog[open]");
  await page.fill("#import-text", exportJson.slice(0, exportJson.indexOf(SECRET) + 12));
  await page.getByRole("button", { name: "Find facts about me" }).click();
  await dialog.getByText(/can't be read/).waitFor({ timeout: 3000 });
  check("a truncated pasted export is refused and nothing sent", previews.length === 0);
  const file = dialog.locator("input[type=file]");
  await file.setInputFiles({ name: "conversations.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify([{ chat_messages: [{ sender: "assistant", text: SECRET }] }])) });
  await dialog.getByText(/no messages written by you/).waitFor({ timeout: 3000 });
  check("an assistant-only export is refused", previews.length === 0);
  const big = path.join(os.tmpdir(), "fareeq-qa-oversized", "conversations.json");
  fs.mkdirSync(path.dirname(big), { recursive: true });
  fs.writeFileSync(big, Buffer.alloc(50 * 1024 * 1024 + 10, 32));
  await file.setInputFiles(big);
  await dialog.getByText(/over 50 MB/).waitFor({ timeout: 10000 });
  check("an oversized file is refused", previews.length === 0);
  await file.setInputFiles({ name: "conversations.json", mimeType: "application/json", buffer: Buffer.from(exportJson) });
  await sleep(300);
  await page.getByRole("button", { name: "Find facts about me" }).click();
  await page.waitForFunction(() => /Tick what Leo|No facts about you/.test(document.querySelector("dialog[open]")?.textContent || ""), null, { timeout: 15000 });
  check("a valid mixed export sends only the person's words", previews.length === 1 && previews[0].includes("pharmacist") && !previews[0].includes(SECRET));
  await page.keyboard.press("Escape");

  // --- 8. drawers fit at every text size, both directions -------------------------------------
  async function drawerFits(label, open) {
    await open();
    const dlg = page.locator("dialog[open]");
    await dlg.waitFor({ timeout: 5000 });
    await sleep(400);
    const fit = await page.evaluate(() => {
      const d = document.querySelector("dialog[open]");
      const w = innerWidth, h = innerHeight;
      const inside = (x, y) => d.contains(document.elementFromPoint(x, y));
      const rtl = document.documentElement.dir === "rtl";
      const phone = w < 640;
      const edge = phone ? w / 2 : rtl ? 8 : w - 8;
      return {
        top: phone ? inside(edge, h * 0.15) : inside(edge, 4),
        bottom: inside(edge, h - 4),
        overflow: document.documentElement.scrollWidth - w,
        scrolls: d.scrollHeight > d.clientHeight ? (d.scrollTop = 99999, d.scrollTop > 0) : true,
      };
    });
    const ok = fit.top && fit.bottom && fit.overflow <= 1 && fit.scrolls;
    check(`${label} fits`, ok, JSON.stringify(fit));
    await page.keyboard.press("Escape");
    await sleep(300);
    check(`${label} closes with Escape`, (await page.locator("dialog[open]").count()) === 0);
  }
  for (const [scale, size] of [["1", { width: 1280, height: 860 }], ["1.5", { width: 1280, height: 860 }], ["1.5", { width: 390, height: 844 }]]) {
    for (const locale of ["en", "ar"]) {
      await api(page, "/users/me", { method: "PATCH", body: JSON.stringify({ locale, ui_preferences: { text_scale: Number(scale) } }) });
      await context.addCookies([{ name: "fareeq_locale", value: locale, url: URL }, { name: "fareeq_a11y", value: scale, url: URL }]);
      await page.setViewportSize(size);
      const tag = `${locale} ${scale === "1" ? "100%" : "150%"} ${size.width}px`;
      await page.goto(`${URL}/agents/career`);
      await page.waitForTimeout(800);
      const templates = locale === "ar" ? "القوالب" : "Templates";
      await drawerFits(`template drawer ${tag}`, () => page.getByRole("button", { name: templates, exact: true }).click());
      const focused = await page.evaluate(() => document.activeElement?.getAttribute("aria-label"));
      check(`focus returns to the template button ${tag}`, focused === templates, String(focused));
      await page.goto(`${URL}/memory`);
      await page.waitForTimeout(800);
      const importLabel = locale === "ar" ? "استورد من ChatGPT أو Claude" : "Import from ChatGPT or Claude";
      await drawerFits(`import drawer ${tag}`, () => page.getByRole("button", { name: importLabel }).click());
    }
  }
  await api(page, "/users/me", { method: "PATCH", body: JSON.stringify({ locale: "en", ui_preferences: { text_scale: 1 } }) });

  await context.addCookies([{ name: "fareeq_locale", value: "en", url: URL }, { name: "fareeq_a11y", value: "1", url: URL }]);
  await page.setViewportSize({ width: 1280, height: 860 });

  // Delayed account verification must not replace a handoff or early typing.
  const owner = (await api(page, "/users/me")).body.id;
  const draftKey = `fareeq.draft.${encodeURIComponent(owner)}.career.new`;
  await page.evaluate(([key]) => localStorage.setItem(key, "OLD-UNSENT-DRAFT"), [draftKey]);
  await page.route("**/api/users/me", async (route) => {
    await sleep(1500);
    await route.continue();
  });
  await page.goto(`${URL}/agents/career?draft=NEW-HANDOFF-EXCERPT`);
  await page.waitForFunction(() => document.querySelector("#composer")?.value === "NEW-HANDOFF-EXCERPT");
  await page.waitForFunction(([key]) => localStorage.getItem(key) === "NEW-HANDOFF-EXCERPT", [draftKey]);
  check("late account verification preserves the handoff", await page.locator("#composer").inputValue() === "NEW-HANDOFF-EXCERPT");
  await page.evaluate(([key]) => localStorage.setItem(key, "OLDER-TEXT"), [draftKey]);
  await page.goto(`${URL}/agents/career?compose=1`);
  await page.locator("#composer").fill("Typed before account arrived");
  await page.waitForFunction(([key]) => localStorage.getItem(key) === "Typed before account arrived", [draftKey]);
  check("late account verification preserves early typing", await page.locator("#composer").inputValue() === "Typed before account arrived");
  await page.unroute("**/api/users/me");
  await page.reload();
  await page.waitForFunction(() => document.querySelector("#composer")?.value === "Typed before account arrived");
  check("ordinary owned chat draft still restores on reload", await page.locator("#composer").inputValue() === "Typed before account arrived");

  // Speech joins the draft; it never sends typed work or staged files.
  const speechBefore = sentSpeech.length;
  await page.fill("#composer", "My typed work");
  await page.getByRole("button", { name: "Talk hands-free", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#composer")?.value.includes("dentist"), null, { timeout: 25000 });
  check("speech preserves typed work without sending", (await page.locator("#composer").inputValue()).startsWith("My typed work") && sentSpeech.length === speechBefore);
  await page.fill("#composer", "");
  await page.locator('input[type=file]').first().setInputFiles({ name: "qa-note.txt", mimeType: "text/plain", buffer: Buffer.from("Synthetic attachment for testing") });
  await page.waitForFunction(() => !document.querySelector('[aria-label="Talk hands-free"]')?.disabled);
  await page.getByRole("button", { name: "Talk hands-free", exact: true }).click();
  await page.waitForFunction(() => document.querySelector("#composer")?.value.includes("dentist"), null, { timeout: 25000 });
  check("speech with a staged attachment stays unsent", sentSpeech.length === speechBefore && await page.getByText("qa-note.txt", { exact: true }).isVisible());

  // CV edits survive both client navigation and a reload before saving.
  await page.goto(`${URL}/cv`);
  await page.getByLabel("Your name").fill("Unsent CV recovery name");
  await page.getByRole("link", { name: "Ask Harvey to review", exact: true }).click();
  await page.waitForURL(/agents\/career/);
  await page.goBack();
  await page.getByLabel("Your name").waitFor();
  check("CV edits survive leaving and returning", await page.getByLabel("Your name").inputValue() === "Unsent CV recovery name");
  page.once("dialog", (dialog) => dialog.accept());
  await page.reload();
  await page.getByLabel("Your name").waitFor();
  check("CV edits survive reload", await page.getByLabel("Your name").inputValue() === "Unsent CV recovery name");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await page.getByRole("button", { name: "All saved", exact: true }).waitFor();
  check("saving clears the CV recovery draft", await page.evaluate(() => !Object.keys(localStorage).some((key) => key.includes(".cv.") && localStorage.getItem(key))));

  // A revoked session must clear drafts through the actual API 401 path.
  await page.goto(`${URL}/agents/career`);
  await page.locator("#composer").fill("PRIVATE-QA-DRAFT-AFTER-REVOCATION");
  await page.waitForFunction(() => Object.keys(localStorage).some((key) =>
    key.startsWith("fareeq.draft.") && localStorage.getItem(key) === "PRIVATE-QA-DRAFT-AFTER-REVOCATION"));
  check("chat draft is bound to the verified account", await page.evaluate(() => {
    const owner = localStorage.getItem("fareeq.draftOwner");
    return !!owner && Object.keys(localStorage).some((key) => key.startsWith(`fareeq.draft.${encodeURIComponent(owner)}.`));
  }));
  await api(page, "/auth/sign-out-everywhere", { method: "POST" });
  await page.goto(`${URL}/account`);
  await page.waitForURL(/\/login/);
  check("revoked authentication clears drafts and handoffs", await page.evaluate(() =>
    !Object.keys(localStorage).some((key) => key.startsWith("fareeq.draft.")) &&
    !localStorage.getItem("fareeq.draftOwner") && !sessionStorage.getItem("fareeq.handoff")));

  check("no page errors", pageErrors.length === 0, pageErrors.slice(0, 4).join(" | "));
  await browser.close();
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => {
  console.error("QA crashed:", e.message);
  process.exit(2);
});
