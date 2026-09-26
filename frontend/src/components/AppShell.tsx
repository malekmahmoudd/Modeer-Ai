"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Brand } from "@/components/Brand";
import { SearchPalette } from "@/components/search/SearchPalette";
import { Icon } from "@/components/ui/Icon";
import { apiFetch, PUBLIC_PAGES, useApi } from "@/lib/api";
import { firstName } from "@/lib/format";
import { PrefsProvider, usePrefs, type Locale } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { clearDrafts, useOnline, useServiceWorker } from "@/lib/offline";
import type { UserProfile } from "@/types";

const NAV: { href: string; label: MessageKey; icon: "home" | "team" | "memory" | "goals" | "calendar" }[] = [
  { href: "/", label: "nav.home", icon: "home" },
  { href: "/team", label: "nav.team", icon: "team" },
  { href: "/memory", label: "nav.memory", icon: "memory" },
  { href: "/goals", label: "nav.goals", icon: "goals" },
  { href: "/plans", label: "nav.plans", icon: "calendar" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/team") return pathname.startsWith("/team") || pathname.startsWith("/agents");
  if (href === "/plans") return pathname.startsWith("/plans") || pathname.startsWith("/week");
  return pathname.startsWith(href);
}

export function AppShell({
  children,
  initialLocale,
  initialSaver,
}: {
  children: React.ReactNode;
  initialLocale: Locale;
  initialSaver: boolean;
}) {
  return (
    <PrefsProvider initialLocale={initialLocale} initialSaver={initialSaver}>
      <Shell>{children}</Shell>
    </PrefsProvider>
  );
}

/** Switches the interface language; saved on the account when signed in. */
export function LanguageToggle({ signedIn, className = "" }: { signedIn: boolean; className?: string }) {
  const { locale, setLocale, t } = usePrefs();
  return (
    <button
      type="button"
      lang={locale === "ar" ? "en" : "ar"}
      aria-label={t("nav.otherLanguageLabel")}
      className={`grid min-h-11 min-w-11 place-items-center px-2 text-sm font-bold underline decoration-pink decoration-2 underline-offset-4 ${className}`}
      onClick={() => {
        const next = locale === "ar" ? "en" : "ar";
        setLocale(next);
        if (signedIn) {
          apiFetch("/users/me", { method: "PATCH", body: JSON.stringify({ locale: next }) }).catch(() => undefined);
        }
      }}
    >
      {t("nav.otherLanguage")}
    </button>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const publicPage = PUBLIC_PAGES.includes(pathname);
  const { t, locale, setLocale } = usePrefs();
  const { data: user } = useApi<UserProfile>(publicPage ? null : "/users/me");
  const name = firstName(user?.display_name);
  const { data: auth } = useApi<{ required: boolean }>("/auth/status");
  const online = useOnline();
  const { updateReady, reload } = useServiceWorker();
  const [searchOpen, setSearchOpen] = useState(false);

  // The language saved on the account follows the person to a new device.
  const saved = user?.locale;
  useEffect(() => {
    if (saved && saved !== locale) setLocale(saved);
    // Only when the account's value arrives or changes, not on every toggle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saved]);

  // Ctrl/⌘-K opens search anywhere.
  useEffect(() => {
    if (publicPage) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [publicPage]);

  const banners = (
    <>
      {!online && (
        <p role="status" className="flex items-center justify-center gap-2 bg-navy px-4 py-2 text-center text-[13px] font-semibold text-paper-hi">
          <Icon name="offline" size={16} /> {t("app.offline")}
        </p>
      )}
      {updateReady && (
        <p role="status" className="flex items-center justify-center gap-3 bg-sun px-4 py-1.5 text-[13px] font-semibold text-ink">
          {t("app.update")}
          <button onClick={reload} className="underline decoration-2 underline-offset-2">
            {t("app.reload")}
          </button>
        </p>
      )}
    </>
  );

  if (publicPage) {
    return (
      <main>
        {banners}
        <div className="fixed end-3 top-3 z-50">
          <LanguageToggle signedIn={false} className="bg-paper-hi" />
        </div>
        {children}
      </main>
    );
  }

  // The agent workspace owns its own full-height layout.
  const inWorkspace = pathname.startsWith("/agents/");
  const atHome = pathname === "/";

  return (
    <div className={`flex min-h-dvh flex-col bg-paper ${atHome ? "sunshine-shell" : ""}`}>
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-50 focus:bg-sun focus:px-3 focus:py-2">
        {t("nav.skip")}
      </a>
      {/* ---------- top navigation ---------- */}
      <header className="sticky top-0 z-40 border-b-2 border-ink bg-paper">
        {banners}
        <div className="mx-auto flex h-[var(--nav-h)] w-full max-w-page items-center gap-6 px-4 sm:px-7">
          <Brand size="sm" />

          <nav className="hidden items-center gap-1 md:flex" aria-label={t("nav.main")}>
            {NAV.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className="relative px-3 py-2 text-[15px] font-bold text-ink transition hover:text-pink-deep"
                >
                  {t(item.label)}
                  <span
                    className={`absolute inset-x-2 -bottom-0.5 h-[4px] rounded-full bg-pink transition-opacity ${
                      active ? "opacity-100" : "opacity-0"
                    }`}
                    aria-hidden
                  />
                </Link>
              );
            })}
          </nav>

          <div className="ms-auto flex items-center gap-1 sm:gap-2">
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="grid h-11 w-11 place-items-center rounded-full text-ink transition hover:bg-sun-pale"
              aria-label={t("nav.search")}
              title={`${t("nav.search")} (Ctrl K)`}
            >
              <Icon name="search" size={20} />
            </button>
            <LanguageToggle signedIn />
            {!atHome && <Link href="/account" className="grid min-h-11 place-items-center px-2 text-sm font-bold underline decoration-pink decoration-2 underline-offset-4">{t("nav.account")}</Link>}
            {!atHome && auth?.required && <button className="text-xs underline" onClick={async () => { await apiFetch("/auth/logout", { method: "POST" }); clearDrafts(); window.location.assign("/login"); }}>{t("nav.signOut")}</button>}
            {name && (
              <Link href="/account" aria-label={t("nav.yourAccount")} className="flex min-h-11 items-center gap-2">
                <span className="hidden text-[13px] font-semibold text-ink-soft sm:inline">{name}</span>
                <span
                  className="grid h-9 w-9 place-items-center rounded-full border-2 border-ink bg-sun text-[13px] font-black"
                  aria-hidden
                >
                  {name.charAt(0).toUpperCase()}
                </span>
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* ---------- page ---------- */}
      <main
        id="main"
        className={
          inWorkspace
            ? "flex min-h-0 flex-1 flex-col"
            : atHome ? "sunshine-main" : "mx-auto w-full max-w-page flex-1 px-4 pb-28 pt-7 sm:px-7 sm:pt-10 md:pb-16"
        }
      >
        {children}
      </main>

      {searchOpen && <SearchPalette onClose={() => setSearchOpen(false)} />}

      {/* ---------- mobile tab bar ---------- */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t-2 border-ink bg-paper pb-[env(safe-area-inset-bottom)] md:hidden"
        aria-label={t("nav.main")}
      >
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className="relative flex min-h-[56px] flex-col items-center justify-center gap-1 text-[11px] font-bold text-ink"
            >
              {active && (
                <span className="absolute inset-x-5 top-0 h-[4px] bg-pink" aria-hidden />
              )}
              <Icon name={item.icon} size={20} className={active ? "text-pink-deep" : "text-ink-soft"} />
              <span className={active ? "text-ink" : "text-ink-soft"}>{t(item.label)}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
