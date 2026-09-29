// The service worker's notification links: only pages of this app are opened.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const ORIGIN = "https://fareeq.example";
const listeners = {};
const context = {
  URL,
  self: {
    location: { origin: ORIGIN },
    addEventListener: (type, fn) => (listeners[type] = fn),
    clients: {},
    registration: {},
  },
  caches: {},
};
vm.createContext(context);
vm.runInContext(readFileSync(new URL("../public/sw.js", import.meta.url), "utf8"), context);
const target = (value) => context.notificationTarget(value, ORIGIN);

test("internal paths are kept", () => {
  assert.equal(target("/plans"), `${ORIGIN}/plans`);
  assert.equal(target("/agents/career?c=1#m-2"), `${ORIGIN}/agents/career?c=1#m-2`);
});

test("anything that could leave the app falls back to the home page", () => {
  for (const bad of [
    "//evil.example/x",
    "/\\evil.example",
    "\\\\evil.example",
    "https://evil.example/plans",
    "javascript:alert(1)",
    "data:text/html,hi",
    "plans",
    "",
    null,
    undefined,
    42,
    { href: "/plans" },
  ]) {
    assert.equal(target(bad), `${ORIGIN}/`, `accepted ${JSON.stringify(bad)}`);
  }
});

function click(url, windows) {
  const opened = [];
  const navigated = [];
  let waited;
  context.self.clients = {
    matchAll: async () => windows,
    openWindow: async (href) => opened.push(href),
  };
  for (const w of windows) {
    w.navigate = async (href) => {
      navigated.push([w.url, href]);
      return w;
    };
    w.focus = async () => w;
  }
  listeners.notificationclick({
    notification: { close() {}, data: { url } },
    waitUntil: (p) => (waited = p),
  });
  return waited.then(() => ({ opened, navigated }));
}

test("an open window of this app is reused; another site's window never is", async () => {
  const { opened, navigated } = await click("//evil.example", [
    { url: "https://fareeq.example.evil.test/" },
    { url: `${ORIGIN}/memory` },
  ]);
  assert.deepEqual(opened, []);
  assert.deepEqual(navigated, [[`${ORIGIN}/memory`, `${ORIGIN}/`]]);
});

test("with no window of this app, a new one opens on the safe target", async () => {
  const { opened } = await click("/plans", [{ url: "https://other.example/" }]);
  assert.deepEqual(opened, [`${ORIGIN}/plans`]);
});
