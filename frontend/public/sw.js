/* Fareeq service worker: an app shell that opens on a weak or missing connection.
 *
 * - Pages: network first, so a deploy is seen at once; the last copy is used
 *   only when the network fails. A page is the shell — personal data arrives
 *   from /api afterwards and is never cached here.
 * - Built files (/_next/static): cache first. Their names change with their
 *   contents, so a cached one can never be stale.
 * - Artwork and icons: cache first, refreshed in the background.
 * - /api/*: never touched. Messages, memories and files stay off the disk.
 *
 * Bump VERSION when this file's behaviour changes; old caches are deleted on
 * activation, and open pages are offered a reload.
 */
const VERSION = "fareeq-v1";
const PAGES = `${VERSION}-pages`;
const STATIC = `${VERSION}-static`;
const OFFLINE_FALLBACK = "/";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(PAGES)
      .then((cache) => cache.add(new Request(OFFLINE_FALLBACK, { credentials: "same-origin" })))
      .catch(() => undefined),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "skip-waiting") self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirst(request));
    return;
  }
  if (url.pathname.startsWith("/_next/static/")) {
    event.respondWith(cacheFirst(request));
    return;
  }
  if (url.pathname.startsWith("/art/") || url.pathname === "/icon.svg" || url.pathname.startsWith("/manifest")) {
    event.respondWith(staleWhileRevalidate(request));
  }
});

async function networkFirst(request) {
  const cache = await caches.open(PAGES);
  try {
    const response = await fetch(request);
    // Only good, same-origin pages; never a redirect to /login or an error.
    if (response.ok && response.type === "basic" && !response.redirected) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return (
      (await cache.match(request)) ||
      (await cache.match(OFFLINE_FALLBACK)) ||
      new Response("You're offline.", { status: 503, headers: { "Content-Type": "text/plain" } })
    );
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(STATIC);
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(STATIC);
  const hit = await cache.match(request);
  const refresh = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => hit);
  return hit || refresh;
}
