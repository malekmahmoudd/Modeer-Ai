import type { Metadata, Viewport } from "next";
import { Archivo_Black, Caveat, Inter, Noto_Sans_Arabic, Permanent_Marker } from "next/font/google";
import { cookies, headers } from "next/headers";
import { connection } from "next/server";

import { AppShell } from "@/components/AppShell";
import { LOCALE_COOKIE, SAVER_COOKIE, type Locale } from "@/lib/i18n/cookies";
import "./globals.css";

/* UI text — highly readable */
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
/* Heavy display — headings, panel names. Decorative: not preloaded, so with
   Data saver on (which swaps it for the system font) it is never downloaded. */
const display = Archivo_Black({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-display",
  display: "swap",
  preload: false,
});
/* Brush wordmark — "Fareeq" only */
const brush = Permanent_Marker({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-brush",
  display: "swap",
  preload: false,
});
/* Arabic: the fonts above have no Arabic glyphs. Loaded only when a page shows
   Arabic text (unicode-range), so Latin pages cost nothing extra. */
const arabic = Noto_Sans_Arabic({
  subsets: ["arabic"],
  weight: "variable",
  variable: "--font-arabic",
  display: "swap",
  preload: false,
});
/* Handwritten margin notes — decorative, sparse */
const hand = Caveat({
  subsets: ["latin"],
  weight: ["700"],
  variable: "--font-hand",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  title: "Fareeq — Personal AI Team",
  description:
    "Leo, your personal assistant, plus a team of specialist AI agents that share your context.",
  applicationName: "Fareeq",
  appleWebApp: { capable: true, title: "Fareeq", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  themeColor: "#FFF7DF",
  viewportFit: "cover",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Render every page per request: each needs its own script nonce (see
  // src/proxy.ts), and a page prerendered at build time would carry none.
  await connection();
  const [store, requestHeaders] = await Promise.all([cookies(), headers()]);
  // The language: the person's choice, else their browser's first preference.
  const chosen = store.get(LOCALE_COOKIE)?.value;
  const locale: Locale =
    chosen === "ar" || chosen === "en"
      ? chosen
      : /^ar\b/i.test(requestHeaders.get("accept-language") ?? "")
        ? "ar"
        : "en";
  // Data saver: their choice, else the browser's own "Save-Data" setting.
  const saverCookie = store.get(SAVER_COOKIE)?.value;
  const dataSaver =
    saverCookie === undefined ? requestHeaders.get("save-data") === "on" : saverCookie === "1";
  return (
    <html
      lang={locale}
      dir={locale === "ar" ? "rtl" : "ltr"}
      className={`${inter.variable} ${display.variable} ${brush.variable} ${hand.variable} ${arabic.variable}${dataSaver ? " data-saver" : ""}`}
    >
      <body className="font-sans">
        <AppShell initialLocale={locale} initialSaver={dataSaver}>
          {children}
        </AppShell>
      </body>
    </html>
  );
}
