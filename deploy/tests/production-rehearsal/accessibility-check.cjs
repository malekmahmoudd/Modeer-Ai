/* Accessibility checks against the production rehearsal (see README.md): an axe-core
   scan (WCAG 2.2 A/AA plus best practice) of every page at desktop and phone width,
   and a keyboard-only pass. Run after browser-check.cjs, on the same stack.
   PLAYWRIGHT_MODULE and AXE_MODULE may point to existing installs; REHEARSAL_URL
   and A11Y_REPORT override the address and the report path.
   This is automated evidence only. It does not replace a pass with a real screen
   reader (NVDA, VoiceOver). */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const fs = require("node:fs");
const path = require("node:path");

const axeSource = fs.readFileSync(
  path.join(path.dirname(require.resolve(process.env.AXE_MODULE || "axe-core")), "axe.min.js"),
  "utf8",
);
const base = process.env.REHEARSAL_URL || "https://localhost:8443";
const report = process.env.A11Y_REPORT || "accessibility-results.json";
const PUBLIC = ["/login", "/signup", "/recover", "/privacy"];
const SIGNED_IN = ["/", "/team", "/memory", "/goals", "/account", "/agents/modeer", "/agents/study"];
const results = { url: base, axe: {}, keyboard: {} };

async function axe(page, name) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(axeSource);
  const run = await page.evaluate(() =>
    window.axe.run(document, {
      runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"],
    }),
  );
  results.axe[name] = run.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes.map((n) => `${n.target.join(" ")}: ${n.failureSummary.replace(/\s+/g, " ")}`),
  }));
  const found = run.violations.map((v) => `${v.id} (${v.impact}) x${v.nodes.length}`);
  console.log(`axe ${name}: ${found.join(", ") || "no violations"}`);
}

// Tab from the top of the page until focus wraps; every stop must be on screen and
// show a focus indicator, on the element itself or on the composer that holds it.
async function keyboard(page, name) {
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.mouse.click(2, 2);
  const seen = [];
  const problems = [];
  for (let i = 0; i < 80; i++) {
    await page.keyboard.press("Tab");
    const stop = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const drawn = (node) => {
        const s = getComputedStyle(node);
        return (s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== "none";
      };
      const holder = el.closest(".sunshine-composer, .workspace-composer form, [class*='focus-within']");
      const box = el.getBoundingClientRect();
      return {
        key: el.outerHTML.slice(0, 120),
        label: (el.getAttribute("aria-label") || el.innerText || el.id || el.tagName).trim().slice(0, 40),
        indicator: drawn(el) || Boolean(holder && (drawn(holder) || holder.className.includes("focus-within"))),
        visible: box.width > 0 && box.height > 0,
      };
    });
    if (!stop || (seen.length && seen[0] === stop.key)) break;
    seen.push(stop.key);
    if (!stop.visible) problems.push(`off-screen stop: ${stop.label}`);
    if (!stop.indicator) problems.push(`no focus indicator: ${stop.label}`);
  }
  results.keyboard[name] = { stops: seen.length, problems };
  console.log(`keys ${name}: ${seen.length} stops${problems.length ? `; ${problems.join("; ")}` : ""}`);
}

(async () => {
  const browser = await chromium.launch({ channel: "chrome" });
  for (const [width, viewport] of [["desktop", { width: 1280, height: 860 }], ["phone", { width: 390, height: 844 }]]) {
    // bypassCSP lets the scanner's script run; the policy itself is checked by browser-check.cjs.
    const context = await browser.newContext({ ignoreHTTPSErrors: true, bypassCSP: true, viewport });
    const page = await context.newPage();
    for (const route of PUBLIC) {
      await page.goto(base + route);
      await axe(page, `${width} ${route}`);
      if (width === "desktop") await keyboard(page, route);
    }
    await page.goto(base + "/login");
    await page.getByRole("button", { name: "Have an invitation key? Use it instead" }).press("Enter");
    await axe(page, `${width} /login (invitation key)`);
    await page.getByLabel("Access key").fill("q".repeat(40));
    await page.getByLabel("Access key").press("Enter");
    await page.waitForURL(base + "/");
    for (const route of SIGNED_IN) {
      await page.goto(base + route);
      await axe(page, `${width} ${route}`);
      if (width === "desktop") await keyboard(page, route);
    }
    await context.close();
  }

  // The one-time recovery code screen, reached with the keyboard.
  const context = await browser.newContext({ ignoreHTTPSErrors: true, bypassCSP: true });
  const page = await context.newPage();
  await page.goto(base + "/signup");
  await page.getByLabel("What should we call you?").fill("Keyboard");
  await page.getByLabel("Email").fill(`keyboard-${Date.now()}@example.com`);
  await page.getByLabel("Password").fill("a long enough passphrase");
  await page.getByLabel("Password").press("Enter");
  await page.getByRole("heading", { name: "Save your recovery codes." }).waitFor();
  await axe(page, "desktop /signup (recovery codes)");
  await page.getByLabel("I've saved these codes").press("Space");
  await page.getByRole("button", { name: "Meet your team" }).press("Enter");
  await page.waitForURL(/\/agents\/modeer/);
  await page.getByRole("textbox").last().press("Enter"); // empty: nothing sent
  await page.getByRole("textbox").last().pressSequentially("hello from the keyboard");
  await page.getByRole("textbox").last().press("Enter");
  await page.getByText("hello from the keyboard").first().waitFor();
  console.log("keys signup to first message: done without a mouse");
  await browser.close();

  fs.writeFileSync(report, JSON.stringify(results, null, 2) + "\n");
  const failures = Object.values(results.axe).flat().length +
    Object.values(results.keyboard).reduce((n, k) => n + k.problems.length, 0);
  console.log(`${failures} finding(s); report written to ${report}`);
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
