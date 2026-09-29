"use client";

import { apiFetch } from "@/lib/api";

/** Whether this browser can show reminders at all. iPhone and iPad need the
 *  app added to the home screen first. */
export function pushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

async function registration(): Promise<ServiceWorkerRegistration | null> {
  if (!pushSupported()) return null;
  return (
    (await navigator.serviceWorker.getRegistration("/")) ??
    (process.env.NODE_ENV === "production"
      ? await navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" })
      : null)
  );
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = base64url.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(base64url.length / 4) * 4, "=");
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

/**
 * Whether this browser gets reminders for the account signed in now. The
 * browser's own subscription is not enough: it may be left from a sign-in that
 * ended or from someone else who used this browser, so the server decides.
 */
export async function pushOn(): Promise<{ on: boolean; leftover: boolean }> {
  // Inspect subscriptions only after permission exists. Some browser engines
  // cannot resolve the push service before then. Never prompt on page load.
  if (!pushSupported() || Notification.permission !== "granted") return { on: false, leftover: false };
  const reg = await registration();
  const sub = await reg?.pushManager.getSubscription();
  if (!sub) return { on: false, leftover: false };
  const { on } = await apiFetch<{ on: boolean }>("/push/device", {
    method: "POST",
    body: JSON.stringify({ endpoint: sub.endpoint }),
  });
  // `leftover`: the browser still listens, but not for this account on this
  // sign-in (turned off by an update, a sign-out, or someone else's).
  return { on, leftover: !on };
}

/** On signing out: this browser stops listening for reminders at all. The
 *  server has already dropped them; this removes the browser's side too. */
export async function forgetPushHere(): Promise<void> {
  try {
    const reg = pushSupported() ? await navigator.serviceWorker.getRegistration("/") : undefined;
    await (await reg?.pushManager.getSubscription())?.unsubscribe();
  } catch {
    /* nothing to forget, or the browser refused: the server side is what counts */
  }
}

export type PushResult = "on" | "denied" | "unsupported" | "unavailable";

/** Asks permission and signs this browser up for reminders. */
export async function enablePush(): Promise<PushResult> {
  const reg = await registration();
  if (!reg) return "unsupported";
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return "denied";
  let key: string;
  try {
    key = (await apiFetch<{ public_key: string }>("/push/key")).public_key;
  } catch {
    return "unavailable";
  }
  await navigator.serviceWorker.ready;
  const sub =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(key) }));
  await apiFetch("/push/subscribe", { method: "POST", body: JSON.stringify(sub.toJSON()) });
  return "on";
}

export async function disablePush(): Promise<void> {
  const sub = await (await registration())?.pushManager.getSubscription();
  if (!sub) return;
  await apiFetch("/push/unsubscribe", { method: "POST", body: JSON.stringify({ endpoint: sub.endpoint }) }).catch(
    () => undefined,
  );
  await sub.unsubscribe();
}
