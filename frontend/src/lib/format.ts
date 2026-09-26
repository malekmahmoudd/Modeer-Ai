import { currentLocale, intlTag, t, translateCount } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";

/** The server keeps times in UTC; some arrive without saying so ("…T09:00:00").
 *  Read those as UTC, not as this device's local time. */
export function parseServerTime(iso: string): Date {
  const zoned = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) || !iso.includes("T");
  return new Date(zoned ? iso : `${iso}Z`);
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const then = parseServerTime(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return t("time.justNow");
  const ago = new Intl.RelativeTimeFormat(intlTag() ?? "en", { numeric: "auto", style: "narrow" });
  if (mins < 60) return ago.format(-mins, "minute");
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return ago.format(-hrs, "hour");
  const days = Math.round(hrs / 24);
  if (days < 7) return ago.format(-days, "day");
  return parseServerTime(iso).toLocaleDateString(intlTag(), { month: "short", day: "numeric" });
}

/** "Thu 1 Oct" from an ISO date, read as a calendar day (no timezone shift). */
export function calendarDay(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(intlTag(), {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** Whole days from today to an ISO calendar date (negative when past). */
export function daysFromToday(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((new Date(y, m - 1, d).getTime() - start.getTime()) / 86400000);
}

/** "Today", "Tomorrow", "In 3 days", "2 days ago". */
export function countdown(iso: string): string {
  const n = daysFromToday(iso);
  if (n === 0) return t("time.today");
  if (n === 1) return t("time.tomorrow");
  if (n === -1) return t("time.yesterday");
  return n > 1
    ? translateCount(currentLocale(), "time.inDays", n)
    : translateCount(currentLocale(), "time.daysAgo", -n);
}

/** A number as the interface language writes it. */
export function formatNumber(value: number, digits = 0): string {
  return new Intl.NumberFormat(intlTag(), { maximumFractionDigits: digits }).format(value);
}

export function firstName(name?: string | null): string | undefined {
  if (!name || name.toLowerCase() === "you") return undefined;
  return name.trim().split(/\s+/)[0];
}

export function greeting(name?: string): string {
  const h = new Date().getHours();
  const part = t(h < 12 ? "greeting.morning" : h < 18 ? "greeting.afternoon" : "greeting.evening");
  return name ? `${part}, ${name}` : `${part}`;
}

const ACRONYMS = new Set([
  "ml", "ai", "cv", "gpa", "id", "url", "api", "llm", "pr", "os", "ui", "ux",
]);

/** "education.field_of_study" / "weak_topics.weak_topic" -> "Field of study" */
export function humanizeKey(key: string): string {
  const last = key.split(".").pop() || key;
  const words = last.replace(/_/g, " ").trim().split(/\s+/);
  return words
    .map((w, i) => {
      if (ACRONYMS.has(w.toLowerCase())) return w.toUpperCase();
      return i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w;
    })
    .join(" ");
}

const CATEGORIES = new Set([
  "education", "career", "goals", "context", "finance", "health",
  "preferences", "weak_topics", "targets", "routine", "general",
]);

export function categoryLabel(category: string): string {
  return CATEGORIES.has(category) ? t(`category.${category}` as MessageKey) : humanizeKey(category);
}

export function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((c) => c + c)
          .join("")
      : clean;
  const n = parseInt(full, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Inline CSS custom property so descendants can use var(--accent). */
export function accentStyle(hex: string): React.CSSProperties {
  return {
    ["--accent" as string]: hex,
    ["--accent-soft" as string]: hexToRgba(hex, 0.14),
  } as React.CSSProperties;
}
