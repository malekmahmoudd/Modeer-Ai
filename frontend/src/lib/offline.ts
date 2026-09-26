"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

/** Whether the browser thinks it has a connection. */
export function useOnline(): boolean {
  return useSyncExternalStore(
    (notify) => {
      window.addEventListener("online", notify);
      window.addEventListener("offline", notify);
      return () => {
        window.removeEventListener("online", notify);
        window.removeEventListener("offline", notify);
      };
    },
    () => navigator.onLine,
    () => true,
  );
}

/**
 * Registers /sw.js (production only: in development it would cache code that
 * is meant to change on every save). `updateReady` turns true when a newer
 * version has installed and is waiting; `reload` switches to it.
 */
export function useServiceWorker() {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);

  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    let cancelled = false;
    navigator.serviceWorker
      .register("/sw.js", { scope: "/", updateViaCache: "none" })
      .then((registration) => {
        if (cancelled) return;
        // A first install is not an update: only offer a reload when a page
        // is already being controlled by an older version.
        const offer = (worker: ServiceWorker | null) => {
          if (worker && navigator.serviceWorker.controller) setWaiting(worker);
        };
        offer(registration.waiting);
        registration.addEventListener("updatefound", () => {
          const incoming = registration.installing;
          incoming?.addEventListener("statechange", () => {
            if (incoming.state === "installed") offer(incoming);
          });
        });
      })
      .catch(() => undefined);
    let reloading = false;
    const onChange = () => {
      if (reloading) return;
      reloading = true;
      window.location.reload();
    };
    navigator.serviceWorker.addEventListener("controllerchange", onChange);
    return () => {
      cancelled = true;
      navigator.serviceWorker.removeEventListener("controllerchange", onChange);
    };
  }, []);

  const reload = useCallback(() => waiting?.postMessage("skip-waiting"), [waiting]);
  return { updateReady: waiting !== null, reload };
}

// --- drafts ------------------------------------------------------------------------------
// What someone was typing survives a reload, a crash or a dropped connection.
// Kept in this browser only; an unreadable store simply means no draft.

const DRAFT_PREFIX = "fareeq.draft.";

export function draftKey(agentId: string, conversationId: string | null): string {
  return `${DRAFT_PREFIX}${agentId}.${conversationId ?? "new"}`;
}

export function readDraft(key: string): string {
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export function writeDraft(key: string, text: string): void {
  try {
    if (text.trim()) window.localStorage.setItem(key, text);
    else window.localStorage.removeItem(key);
  } catch {
    /* storage full or blocked: the draft just isn't kept */
  }
}

/** Forget every saved draft (on sign-out, so the next person can't read them). */
export function clearDrafts(): void {
  try {
    for (const key of Object.keys(window.localStorage)) {
      if (key.startsWith(DRAFT_PREFIX)) window.localStorage.removeItem(key);
    }
  } catch {
    /* nothing to clear */
  }
}
