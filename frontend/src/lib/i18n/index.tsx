"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { ar } from "@/lib/i18n/ar";
import { LOCALE_COOKIE, SAVER_COOKIE, type Locale } from "@/lib/i18n/cookies";
import { en, type MessageKey } from "@/lib/i18n/en";

export { LOCALE_COOKIE, SAVER_COOKIE, type Locale };

/**
 * Interface language and Data saver.
 *
 * The server reads both from cookies (see app/layout.tsx), so the first paint
 * already has the right `lang`, `dir` and fonts. Changing either here writes
 * the cookie and updates the page in place; the language is also saved on the
 * account so it follows the person to their other devices.
 */

const DICTIONARIES: Record<Locale, Record<string, string | undefined>> = { en, ar };

/** Keys counted with `tn`: "today.goals" for "today.goals_one" / "_other". */
export type CountKey = {
  [K in MessageKey]: K extends `${infer Base}_other` ? Base : never;
}[MessageKey];

type Vars = Record<string, string | number>;

// For code outside React (formatting helpers, upload errors). The server has
// already written the language into <html lang>, so it is right from the start.
let active: Locale =
  typeof document !== "undefined" && document.documentElement.lang === "ar" ? "ar" : "en";

export function currentLocale(): Locale {
  return active;
}

/** The locale tag for Intl: Arabic as written in Egypt (Arabic-Indic digits). */
export function intlTag(locale: Locale = active): string | undefined {
  return locale === "ar" ? "ar-EG" : undefined;
}

export function translate(locale: Locale, key: MessageKey, vars?: Vars): string {
  const text = DICTIONARIES[locale][key] ?? en[key] ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) =>
    vars[name] !== undefined ? String(vars[name]) : whole,
  );
}

/** A counted phrase in the grammatical form the number needs. Arabic has six
 *  (zero, one, two, few, many, other); a missing form falls back to "other". */
export function translateCount(locale: Locale, key: CountKey, n: number, vars?: Vars): string {
  const dictionary = DICTIONARIES[locale];
  const form = new Intl.PluralRules(locale).select(n);
  const chosen = `${key}_${form}` in dictionary ? `${key}_${form}` : `${key}_other`;
  const shown = new Intl.NumberFormat(intlTag(locale)).format(n);
  return translate(locale, chosen as MessageKey, { n: shown, ...vars });
}

/** Plain-JS access for non-component code. */
export const t = (key: MessageKey, vars?: Vars) => translate(active, key, vars);

function writeCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/; max-age=31536000; samesite=lax`;
}

interface Prefs {
  locale: Locale;
  dir: "ltr" | "rtl";
  dataSaver: boolean;
  setLocale: (locale: Locale) => void;
  setDataSaver: (on: boolean) => void;
  t: (key: MessageKey, vars?: Vars) => string;
  tn: (key: CountKey, n: number, vars?: Vars) => string;
}

const PrefsContext = createContext<Prefs | null>(null);

export function PrefsProvider({
  initialLocale,
  initialSaver,
  children,
}: {
  initialLocale: Locale;
  initialSaver: boolean;
  children: React.ReactNode;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const [dataSaver, setSaverState] = useState(initialSaver);

  const setLocale = useCallback((next: Locale) => {
    active = next;
    writeCookie(LOCALE_COOKIE, next);
    document.documentElement.lang = next;
    document.documentElement.dir = next === "ar" ? "rtl" : "ltr";
    setLocaleState(next);
  }, []);

  const setDataSaver = useCallback((on: boolean) => {
    writeCookie(SAVER_COOKIE, on ? "1" : "0");
    document.documentElement.classList.toggle("data-saver", on);
    setSaverState(on);
  }, []);

  const value = useMemo<Prefs>(
    () => ({
      locale,
      dir: locale === "ar" ? "rtl" : "ltr",
      dataSaver,
      setLocale,
      setDataSaver,
      t: (key, vars) => translate(locale, key, vars),
      tn: (key, n, vars) => translateCount(locale, key, n, vars),
    }),
    [locale, dataSaver, setLocale, setDataSaver],
  );

  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): Prefs {
  const prefs = useContext(PrefsContext);
  if (!prefs) throw new Error("usePrefs outside PrefsProvider");
  return prefs;
}

/** Shorthand for components that only need text. */
export function useT() {
  const { t: tr, tn, locale } = usePrefs();
  return { t: tr, tn, locale };
}
