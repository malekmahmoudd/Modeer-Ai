/**
 * Where a link in a model's reply may point. Anything refused renders as plain text.
 *
 * Allowed: http(s) and mailto URLs, and links within this app ("/memory", "#part").
 * Refused, because each can take someone somewhere other than it appears to:
 *  - every other scheme: javascript:, data:, vbscript:, file: and the rest;
 *  - protocol-relative "//host" links, which leave the site while looking local;
 *  - backslashes, which browsers read as slashes, so "/\host" means "//host";
 *  - whitespace and control characters, which browsers strip, so "java\tscript:"
 *    means "javascript:";
 *  - bare relative paths ("notes.html"), which resolve against whatever page is open.
 */
const HERE = "https://modeer.invalid";
const SCHEMES = new Set(["http:", "https:", "mailto:"]);

export function safeHref(raw: string): string | null {
  const href = raw.trim();
  if (!href || /[\s\\]/.test(href) || [...href].some((c) => c.charCodeAt(0) < 0x20 || c.charCodeAt(0) === 0x7f)) {
    return null;
  }
  if (href.startsWith("#")) return href;
  if (href.startsWith("/")) {
    if (href.startsWith("//")) return null;
    return new URL(href, HERE).origin === HERE ? href : null;
  }
  try {
    const url = new URL(href);
    return SCHEMES.has(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
