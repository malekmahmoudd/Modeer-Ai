/**
 * The key a quick-note save is sent with, kept until the server confirms it.
 *
 * A save whose answer never arrived may or may not have been stored. Sending
 * the same items again must reuse its key, so the server recognises the retry
 * instead of saving twice, even after "Find what to keep" runs again, Cancel,
 * or a reload. So the key is remembered per set of items (a hash of them, not
 * the items themselves) in this tab's session storage, for up to a day, the
 * time the server keeps its receipts.
 */

export const STORE_KEY = "fareeq.captureKeys";
export const KEEP_MS = 24 * 60 * 60 * 1000;

/** Where keys are kept: sessionStorage in the app; anything alike in tests. */
export interface KeyStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

type Entries = Record<string, { key: string; at: number }>;

// Used when storage is unavailable (private mode, blocked): survives a
// remount, not a reload.
const memory: Entries = {};

function sessionStore(): KeyStore | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

function load(store: KeyStore | null, now: number): Entries {
  let entries: Entries = memory;
  if (store) {
    try {
      const raw = store.getItem(STORE_KEY);
      entries = raw ? (JSON.parse(raw) as Entries) : {};
    } catch {
      entries = { ...memory };
    }
  }
  for (const [id, entry] of Object.entries(entries)) {
    if (!entry || typeof entry.key !== "string" || now - entry.at > KEEP_MS) delete entries[id];
  }
  return entries;
}

function write(store: KeyStore | null, entries: Entries) {
  for (const id of Object.keys(memory)) delete memory[id];
  Object.assign(memory, entries);
  if (!store) return;
  try {
    if (Object.keys(entries).length) store.setItem(STORE_KEY, JSON.stringify(entries));
    else store.removeItem(STORE_KEY);
  } catch {
    /* kept in memory for this page instead */
  }
}

/** Items in a stable order and form, so the same items give the same id. */
function canonical(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value as Record<string, unknown>)
        .sort()
        .map((k) => [k, canonical((value as Record<string, unknown>)[k])]),
    );
  }
  return value;
}

/** A short hash naming a set of items (FNV-1a, twice, 64 bits). Not secret:
 *  only used to find the key again; the items are never stored. */
export function itemsId(items: unknown): string {
  const text = JSON.stringify(canonical(items));
  let a = 0x811c9dc5;
  let b = 0x01000193 ^ text.length;
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i);
    a = Math.imul(a ^ c, 0x01000193) >>> 0;
    b = Math.imul(b ^ c, 0x5bd1e995) >>> 0;
  }
  return a.toString(16).padStart(8, "0") + b.toString(16).padStart(8, "0");
}

function newKey(): string {
  // getRandomValues also works over plain http, unlike randomUUID.
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (x) => x.toString(16).padStart(2, "0")).join("");
}

/** The key to save these items with: the one already used for them if a save
 *  of them is unconfirmed, else a new one, remembered before it is sent. */
export function keyFor(items: unknown, store: KeyStore | null = sessionStore(), now = Date.now()): string {
  const entries = load(store, now);
  const id = itemsId(items);
  const found = entries[id];
  if (found) return found.key;
  const key = newKey();
  entries[id] = { key, at: now };
  write(store, entries);
  return key;
}

/** The server answered for these items (saved, or refused so nothing was
 *  saved): the key is no longer needed. */
export function settle(items: unknown, store: KeyStore | null = sessionStore(), now = Date.now()): void {
  const entries = load(store, now);
  delete entries[itemsId(items)];
  write(store, entries);
}

/** Signing out: forget every key. */
export function forgetKeys(store: KeyStore | null = sessionStore()): void {
  write(store, {});
}
