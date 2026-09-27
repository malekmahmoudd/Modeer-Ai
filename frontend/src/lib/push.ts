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

/** Whether this browser already receives reminders. */
export async function pushOn(): Promise<boolean> {
  const reg = await registration();
  return Boolean(await reg?.pushManager.getSubscription());
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
