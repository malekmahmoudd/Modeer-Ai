import { NextResponse, type NextRequest } from "next/server";

/**
 * A per-request Content Security Policy with a script nonce.
 *
 * Next reads this policy from the request, finds the nonce and puts it on every
 * script tag it renders, so inline scripts need no 'unsafe-inline': an injected
 * <script> without the nonce does not run. 'strict-dynamic' lets the scripts
 * Next loads load their own chunks.
 *
 * Styles keep 'unsafe-inline': components set style="" attributes, and a nonce
 * cannot cover an attribute. The page's scripts are the injection risk; the
 * rest of the policy still keeps every request on this origin.
 *
 * Caddy adds its own fallback policy only to responses that carry none (API
 * responses, static files), so this one is what pages are held to.
 */
export function proxy(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const development = process.env.NODE_ENV !== "production";
  const policy = [
    "default-src 'self'",
    // The development server's fast refresh needs eval; production never does.
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src 'self'${development ? " ws:" : ""}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("content-security-policy", policy);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("content-security-policy", policy);
  return response;
}

export const config = {
  matcher: [
    {
      // Pages only: the API, built assets and artwork carry no inline script.
      source: "/((?!api|_next/static|_next/image|art/|icon.svg).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
