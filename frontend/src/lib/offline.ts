"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

export { draftKey, readDraft, writeDraft, clearDrafts } from "@/lib/drafts";

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
