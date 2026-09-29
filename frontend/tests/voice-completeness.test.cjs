const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const ts = require("typescript");

test("long replies use the complete device voice without a provider request", async () => {
  const spoken = [];
  const exports = {};
  const source = ts.transpileModule(fs.readFileSync(require.resolve("../src/lib/voice.ts"), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS },
  }).outputText;
  vm.runInNewContext(source, {
    exports,
    require: () => ({ API_BASE: "/api", apiFetch: () => { throw Error("No status request expected"); } }),
    DOMException,
    fetch: () => { throw Error("No synthesis request expected"); },
    SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } },
    window: { speechSynthesis: {
      getVoices: () => [{ lang: "en-GB", localService: true }],
      cancel() {},
      speak: (utterance) => spoken.push(utterance),
    } },
  });
  const text = "A".repeat(1600) + ". Final sentence.";
  const reading = await exports.speak(text);
  assert.equal(spoken.map((u) => u.text).join(" "), text);
  reading.stop();
  await reading.done;
  await assert.rejects(exports.speakNaturally(text), /complete long reply/);
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(exports.speak(text, controller.signal), { name: "AbortError" });
  assert.equal(spoken.length, 2);
});
