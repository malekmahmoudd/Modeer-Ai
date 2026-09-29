/** Account-bound browser drafts. Legacy, unowned drafts are never restored. */
import { forgetKeys } from "./captureKeys.ts";

export const ACCOUNT_KEY = "fareeq.draftOwner";
const PREFIX = "fareeq.draft.";
let account: string | null = null;

function store(): Storage | null {
  try { return typeof window === "undefined" ? null : window.localStorage; }
  catch { return null; }
}

export function clearDrafts(): void {
  account = null;
  forgetKeys();
  try {
    const storage = store();
    if (storage) {
      for (const key of Object.keys(storage)) {
        if (key.startsWith(PREFIX)) storage.removeItem(key);
      }
      storage.removeItem(ACCOUNT_KEY);
    }
    if (typeof window !== "undefined") window.sessionStorage.removeItem("fareeq.handoff");
  } catch { /* Blocked storage is never restored. */ }
}

/** Called only after the server identifies the signed-in account. */
export function activateAccount(id: string): void {
  const storage = store();
  try {
    if (storage?.getItem(ACCOUNT_KEY) !== id) clearDrafts();
    storage?.setItem(ACCOUNT_KEY, id);
    account = id;
  } catch { account = null; }
}

export function draftKey(userId: string, agentId: string, conversationId: string | null): string {
  return `${PREFIX}${encodeURIComponent(userId)}.${agentId}.${conversationId ?? "new"}`;
}

function owned(key: string, storage: Storage): boolean {
  return Boolean(account && storage.getItem(ACCOUNT_KEY) === account &&
    key.startsWith(`${PREFIX}${encodeURIComponent(account)}.`));
}

export function readDraft(key: string): string {
  try {
    const storage = store();
    return storage && owned(key, storage) ? storage.getItem(key) ?? "" : "";
  } catch { return ""; }
}

export function writeDraft(key: string, text: string): void {
  try {
    const storage = store();
    if (!storage || !owned(key, storage)) return;
    if (text.trim()) storage.setItem(key, text);
    else storage.removeItem(key);
  } catch { /* A blocked store simply means no saved draft. */ }
}
