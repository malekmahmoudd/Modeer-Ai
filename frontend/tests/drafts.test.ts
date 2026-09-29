import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import * as drafts from "../src/lib/drafts.ts";
import { activateAccount, clearDrafts, draftKey, readDraft, writeDraft, ACCOUNT_KEY } from "../src/lib/drafts.ts";

function storage() {
  const data: Record<string, string> = {};
  return Object.defineProperties(data, {
    getItem: { value: (key: string) => data[key] ?? null },
    setItem: { value: (key: string, value: string) => { data[key] = value; } },
    removeItem: { value: (key: string) => { delete data[key]; } },
  }) as unknown as Storage;
}

test("expiry and account switching cannot expose or recreate another account's draft", () => {
  const localStorage = storage(), sessionStorage = storage();
  Object.defineProperty(globalThis, "window", { configurable: true, value: { localStorage, sessionStorage } });
  try {
    localStorage.setItem("fareeq.draft.career.new", "legacy private text");
    activateAccount("alice");
    assert.equal(localStorage.getItem("fareeq.draft.career.new"), null);
    const alice = draftKey("alice", "career", null);
    const bob = draftKey("bob", "career", null);
    writeDraft(alice, "Alice private text");
    activateAccount("alice"); // repeated /me fetch or reload preserves same-account work
    assert.equal(readDraft(alice), "Alice private text");
    assert.equal(readDraft(bob), "");
    sessionStorage.setItem("fareeq.handoff", "private passage");
    clearDrafts(); // the same cleanup used by every 401 path
    assert.equal(localStorage.getItem(alice), null);
    assert.equal(sessionStorage.getItem("fareeq.handoff"), null);
    writeDraft(alice, "late render after sign-out");
    assert.equal(localStorage.getItem(alice), null);
    activateAccount("bob");
    assert.equal(readDraft(alice), "");
    writeDraft(alice, "stale Alice callback");
    assert.equal(localStorage.getItem(alice), null);
    writeDraft(bob, "Bob text");
    assert.equal(readDraft(bob), "Bob text");
    localStorage.setItem(ACCOUNT_KEY, "alice"); // account changed in another tab
    writeDraft(bob, "stale Bob callback");
    assert.equal(localStorage.getItem(bob), "Bob text");
    assert.equal(readDraft(bob), "");
  } finally {
    clearDrafts();
    Reflect.deleteProperty(globalThis, "window");
  }
});

test("an actual API 401 purges private storage before redirecting", async () => {
  const localStorage = storage(), sessionStorage = storage();
  let redirected = "";
  const window = {
    localStorage, sessionStorage,
    location: { pathname: "/agents/career", assign: (url: string) => { redirected = url; } },
  };
  Object.defineProperty(globalThis, "window", { configurable: true, value: window });
  try {
    activateAccount("alice");
    const key = draftKey("alice", "career", null);
    writeDraft(key, "Private draft");
    const exports: { apiFetch?: (path: string) => Promise<unknown> } = {};
    const code = ts.transpileModule(fs.readFileSync(new URL("../src/lib/api.ts", import.meta.url), "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS },
    }).outputText;
    vm.runInNewContext(code, {
      exports, window, process: { env: {} },
      require: (name: string) => name.includes("drafts") ? drafts : {},
      fetch: async () => ({ status: 401, ok: false, statusText: "Unauthorized", json: async () => ({ detail: "Sign in" }) }),
    });
    await assert.rejects(exports.apiFetch!("/users/me"), /Sign in/);
    assert.equal(redirected, "/login");
    assert.equal(localStorage.getItem(key), null);
    activateAccount("bob");
    assert.equal(readDraft(key), "");
  } finally {
    clearDrafts();
    Reflect.deleteProperty(globalThis, "window");
  }
});
