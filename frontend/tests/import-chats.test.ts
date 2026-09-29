// Import parsing: only the person's own messages ever leave the browser, and a
// broken export is refused rather than sent as it is.
import assert from "node:assert/strict";
import { test } from "node:test";

import { IMPORT_FILE_MAX, IMPORT_LIMIT, readExport, readFile, readPasted } from "../src/lib/importChats.ts";

const ASSISTANT = "ASSISTANT-SECRET-REPLY";

const chatgpt = [
  {
    title: "Job",
    mapping: {
      a: { message: { author: { role: "system" }, content: { parts: ["system prompt"] } } },
      b: { message: { author: { role: "user" }, content: { parts: ["I work as a data analyst in Cairo"] } } },
      c: { message: { author: { role: "assistant" }, content: { parts: [ASSISTANT] } } },
      d: { message: null },
      e: { message: { author: { role: "user" }, content: { parts: [{ image: true }, "What is SQL?"] } } },
    },
  },
];

const claudeExport = [
  {
    name: "Chat",
    chat_messages: [
      { sender: "human", text: "My name is Sara and I prefer short answers" },
      { sender: "assistant", text: ASSISTANT },
      { sender: "human", text: "", content: [{ type: "text", text: "I live in Riyadh" }] },
    ],
  },
];

test("a ChatGPT export keeps only the person's messages, personal ones first", () => {
  const r = readExport(JSON.stringify(chatgpt));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.ok(r.text.startsWith("I work as a data analyst in Cairo"));
  assert.ok(r.text.includes("What is SQL?"));
  assert.ok(!r.text.includes(ASSISTANT) && !r.text.includes("system prompt"));
});

test("a Claude export keeps only human messages, including content parts", () => {
  const r = readExport(JSON.stringify(claudeExport));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.ok(r.text.includes("Sara") && r.text.includes("Riyadh"));
  assert.ok(!r.text.includes(ASSISTANT));
});

test("a truncated export is refused, never sent raw", () => {
  const whole = JSON.stringify(chatgpt);
  const cut = whole.slice(0, whole.indexOf(ASSISTANT) + 10);
  assert.deepEqual(readExport(cut), { ok: false, reason: "malformed" });
  // Pasted, it is treated as an export too, not as notes.
  assert.deepEqual(readPasted(cut), { ok: false, reason: "malformed" });
});

test("malformed message shapes are skipped, and an export with no valid user message is refused", () => {
  const weird = [
    {
      mapping: {
        x: { message: { author: "user", content: { parts: [ASSISTANT] } } },
        y: { message: { author: { role: "user" }, content: "not parts" } },
        z: { message: { author: { role: "user" }, content: { parts: "a string" } } },
      },
    },
    { chat_messages: [{ sender: "human", text: 42 }, { sender: "human" }, "junk"] },
  ];
  assert.deepEqual(readExport(JSON.stringify(weird)), { ok: false, reason: "noUserMessages" });
});

test("an assistant-only export is refused", () => {
  const onlyAssistant = [{ chat_messages: [{ sender: "assistant", text: ASSISTANT }] }];
  assert.deepEqual(readExport(JSON.stringify(onlyAssistant)), { ok: false, reason: "noUserMessages" });
});

test("JSON that is not a known export is refused", () => {
  assert.deepEqual(readExport(JSON.stringify({ messages: [{ role: "user", content: "hi" }] })), {
    ok: false,
    reason: "unrecognised",
  });
  assert.deepEqual(readPasted('["just", "strings"]'), { ok: false, reason: "unrecognised" });
});

test("plain notes pass through, capped at the server's limit", () => {
  const notes = "I work as a nurse. I have two kids.";
  assert.deepEqual(readPasted(`  ${notes}\n`), { ok: true, text: notes, messages: 0 });
  const long = "x".repeat(IMPORT_LIMIT + 500);
  const r = readPasted(long);
  assert.ok(r.ok && r.text.length === IMPORT_LIMIT);
  assert.deepEqual(readPasted("   "), { ok: false, reason: "empty" });
});

test("an export stays within the limit", () => {
  const many = [
    {
      chat_messages: Array.from({ length: 400 }, (_, i) => ({ sender: "human", text: `message ${i} `.repeat(20) })),
    },
  ];
  const r = readExport(JSON.stringify(many));
  assert.ok(r.ok && r.text.length <= IMPORT_LIMIT);
});

test("an oversized file is refused before it is read", async () => {
  let read = false;
  const huge = {
    name: "conversations.json",
    size: IMPORT_FILE_MAX + 1,
    text: async () => {
      read = true;
      return "[]";
    },
  };
  assert.deepEqual(await readFile(huge), { ok: false, reason: "tooBig" });
  assert.equal(read, false);
});

test("a .json file must be an export; a .txt file is notes", async () => {
  const file = (name: string, body: string) => ({ name, size: body.length, text: async () => body });
  assert.deepEqual(await readFile(file("conversations.json", "{oops")), { ok: false, reason: "malformed" });
  assert.equal((await readFile(file("notes.txt", "I study law"))).ok, true);
  const mixed = await readFile(file("conversations.json", JSON.stringify(chatgpt)));
  assert.ok(mixed.ok && !mixed.text.includes(ASSISTANT));
});
