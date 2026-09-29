const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

function load(permission, supported = true, active = true) {
  const calls = [];
  const exports = {};
  const Notification = { permission, requestPermission() { throw Error("Must not request permission on page load"); } };
  const window = supported ? { Notification, PushManager: class {} } : {};
  const navigator = { serviceWorker: { async getRegistration() {
    calls.push("registration");
    return { pushManager: { async getSubscription() {
      calls.push("subscription");
      return { endpoint: "https://example.invalid/synthetic-subscription" };
    } } };
  } } };
  const source = ts.transpileModule(fs.readFileSync(require.resolve("../src/lib/push.ts"), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  vm.runInNewContext(source, {
    exports, window, navigator, Notification, process: { env: { NODE_ENV: "production" } },
    require: () => ({ async apiFetch(path) { calls.push(path); return { on: active }; } }),
  });
  return { pushOn: exports.pushOn, calls };
}

for (const permission of ["default", "denied"]) {
  test(`Account avoids the push service when notification permission is ${permission}`, async () => {
    const { pushOn, calls } = load(permission);
    assert.equal(JSON.stringify(await pushOn()), '{"on":false,"leftover":false}');
    assert.deepEqual(calls, []);
  });
}
test("unsupported browsers do not inspect subscriptions", async () => {
  const { pushOn, calls } = load("granted", false);
  assert.equal((await pushOn()).on, false);
  assert.deepEqual(calls, []);
});
for (const active of [true, false]) {
  test(`granted permission still checks server ownership (active=${active})`, async () => {
    const { pushOn, calls } = load("granted", true, active);
    const state = await pushOn();
    assert.equal(state.on, active);
    assert.equal(state.leftover, !active);
    assert.deepEqual(calls, ["registration", "subscription", "/push/device"]);
  });
}
