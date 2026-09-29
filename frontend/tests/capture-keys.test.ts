// Quick-note retry keys: the same items keep the same key until the server
// answers, across Find again, Cancel and a reload; nothing of the note is stored.
import assert from "node:assert/strict";
import { test } from "node:test";

import { forgetKeys, itemsId, keyFor, KEEP_MS, settle, STORE_KEY, type KeyStore } from "../src/lib/captureKeys.ts";

function storage(): KeyStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

const note = {
  checkins: [{ agent_id: "fitness", text: "Swam 1 km", amount: 1, unit: "km", details: null }],
  followups: [{ agent_id: "career", title: "Dentist on Thursday", due_on: "2026-10-01", ends_on: null }],
};

test("an unconfirmed save keeps its key for the same items", () => {
  const store = storage();
  const first = keyFor(note, store);
  assert.match(first, /^[0-9a-f]{32}$/);
  // Find again gives equal items as new objects, in another key order: same key.
  const refound = JSON.parse(JSON.stringify({ followups: note.followups, checkins: note.checkins }));
  assert.equal(keyFor(refound, store), first);
});

test("the key survives a reload (a new page reading the same session storage)", () => {
  const store = storage();
  const first = keyFor(note, store);
  const afterReload: KeyStore = { getItem: store.getItem, setItem: store.setItem, removeItem: store.removeItem };
  assert.equal(keyFor(note, afterReload), first);
});

test("different items get a different key", () => {
  const store = storage();
  const all = keyFor(note, store);
  const fewer = keyFor({ ...note, followups: [] }, store);
  assert.notEqual(all, fewer);
});

test("once the server answers, the next save of the same items is a new note", () => {
  const store = storage();
  const first = keyFor(note, store);
  settle(note, store);
  assert.notEqual(keyFor(note, store), first);
});

test("keys are forgotten after a day, and on sign-out", () => {
  const store = storage();
  const now = 1_000_000;
  const first = keyFor(note, store, now);
  assert.equal(keyFor(note, store, now + KEEP_MS - 1), first);
  assert.notEqual(keyFor(note, store, now + KEEP_MS + 1), first);
  forgetKeys(store);
  assert.equal(store.data.has(STORE_KEY), false);
});

test("the note's words are never stored, only a hash naming them", () => {
  const store = storage();
  keyFor(note, store);
  const saved = store.data.get(STORE_KEY) ?? "";
  for (const words of ["Swam", "Dentist", "Thursday", "fitness", "career"]) assert.ok(!saved.includes(words));
  assert.ok(saved.includes(itemsId(note)));
});

test("storage that throws falls back to memory for this page", () => {
  const broken: KeyStore = {
    getItem: () => {
      throw new Error("blocked");
    },
    setItem: () => {
      throw new Error("blocked");
    },
    removeItem: () => {
      throw new Error("blocked");
    },
  };
  const first = keyFor(note, broken);
  assert.equal(keyFor(note, broken), first);
});
