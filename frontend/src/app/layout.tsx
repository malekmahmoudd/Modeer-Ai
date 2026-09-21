import type { Metadata, Viewport } from "next";
import { Archivo_Black, Caveat, Inter, Permanent_Marker } from "next/font/google";
import { connection } from "next/server";

import { AppShell } from "@/components/AppShell";
import "./globals.css";

/* UI text — highly readable */
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
/* Heavy display — headings, panel names */
const display = Archivo_Black({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-display",
  display: "swap",
});
/* Brush wordmark — "CrewAi" only */
const brush = Permanent_Marker({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-brush",
  display: "swap",
});
/* Handwritten margin notes — decorative, sparse */
const hand = Caveat({
  subsets: ["latin"],
  weight: ["700"],
  variable: "--font-hand",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CrewAi — Personal AI Team",
  description:
    "Leo, your personal assistant, plus a team of specialist AI agents that share your context.",
};

export const viewport: Viewport = {
  themeColor: "#FFF7DF",
  viewportFit: "cover",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Render every page per request: each needs its own script nonce (see
  // src/proxy.ts), and a page prerendered at build time would carry none.
  await connection();
  return (
    <html
      lang="en"
      className={`${inter.variable} ${display.variable} ${brush.variable} ${hand.variable}`}
    >
      <body className="font-sans">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
