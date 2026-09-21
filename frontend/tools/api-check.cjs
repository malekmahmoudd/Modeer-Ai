// Exercise the actual data hook with controlled request ordering and lifecycle.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const Module = require("node:module");
const ts = require("typescript");
require.extensions[".ts"] = (module, filename) => module._compile(
  ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, filename,
);
const states = [], refs = [];
let stateIndex = 0, refIndex = 0, effect;
const original = Module._load;
Module._load = function (name, ...args) {
  if (name === "react") return {
    useCallback: (fn) => fn,
    useEffect: (fn) => { effect = fn; },
    useRef: (value) => refs[refIndex++] ||= { current: value },
    useState: (value) => {
      const i = stateIndex++;
      if (!(i in states)) states[i] = value;
      return [states[i], (next) => { states[i] = next; }];
    },
  };
  return original.call(this, name, ...args);
};
const { useApi } = require("../src/lib/api.ts");
Module._load = original;
const pending = [];
global.fetch = () => new Promise((resolve, reject) => pending.push({ resolve, reject }));
function render(path) { stateIndex = refIndex = 0; return useApi(path); }
const flush = () => new Promise((resolve) => setImmediate(resolve));
const answer = (request, value) => request.resolve(Response.json(value));

(async () => {
  let hook = render("/memory/shared");
  let cleanup = effect();
  const older = pending.shift();
  const fresh = hook.refetch();
  const newer = pending.shift();
  answer(older, ["old"]);
  await flush();
  assert.equal(states[0], null);
  assert.equal(states[1], true, "stale finally must not clear current loading");
  answer(newer, ["new"]);
  await fresh;
  assert.deepEqual(states[0], ["new"]);

  const oldFailure = hook.refetch();
  const failed = pending.shift();
  const newSuccess = hook.refetch();
  answer(pending.shift(), ["newest"]);
  await newSuccess;
  failed.reject(new Error("obsolete failure"));
  await oldFailure;
  assert.deepEqual(states[0], ["newest"]);
  assert.equal(states[2], null, "stale errors must not replace success");

  const beforeNavigation = hook.refetch();
  const stalePath = pending.shift();
  cleanup();
  hook = render("/goals");
  cleanup = effect();
  answer(stalePath, ["wrong path"]);
  await beforeNavigation;
  answer(pending.shift(), ["goals"]);
  await flush();
  assert.deepEqual(states[0], ["goals"]);

  const beforeUnmount = hook.refetch();
  const staleUnmount = pending.shift();
  cleanup();
  render(null);
  effect();
  answer(staleUnmount, ["must not return"]);
  await beforeUnmount;
  assert.equal(states[0], null);
  assert.equal(states[1], false);
  assert.equal(states[2], null);
  console.log("Data hook: stale results/errors/loading ignored; lifecycle invalidation passed.");
})().catch((e) => { console.error(e); process.exitCode = 1; });
