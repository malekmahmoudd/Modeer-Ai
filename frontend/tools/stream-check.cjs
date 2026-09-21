// Exercise the real stream hook with a scripted response, without a browser.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const Module = require("node:module");
const ts = require("typescript");
require.extensions[".ts"] = (module, filename) => {
  module._compile(ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, filename);
};
const original = Module._load;
Module._load = function (name, ...args) {
  if (name === "@/lib/api") return { API_BASE: "/api" };
  if (name === "react") return {
    useCallback: (fn) => fn, useEffect: () => {},
    useRef: (value) => ({ current: value }), useState: (value) => [value, () => {}],
  };
  return original.call(this, name, ...args);
};
const { useChatStream } = require("../src/features/chat/useChatStream.ts");
Module._load = original;
const notice = "Your reply was saved, but memory could not be updated.";
const frames = [
  { type: "start", conversation_id: "c", context: {} },
  { type: "delta", text: "Saved answer" },
  { type: "end", conversation_id: "c", content: "Saved answer", completion: "completed" },
  { type: "memory", memory_candidates: [], newly_onboarded: false, error: notice },
].map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
global.fetch = async () => new Response(frames);
const received = [];
const chat = useChatStream("study", {
  onEnd: (event) => received.push(["reply", event]),
  onMemory: (event) => received.push(["memory", event]),
  onError: (error) => { throw new Error(error); },
});
chat.send("Hello", null).then(() => {
  assert.equal(received[0][1].completion, "completed");
  assert.equal(received[0][1].content, "Saved answer");
  assert.equal(received[1][1].error, notice);
  console.log("Completed reply preserved; memory failure delivered separately.");
}).catch((err) => { console.error(err); process.exitCode = 1; });
