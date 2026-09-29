/**
 * Text size, high contrast and reduced motion, for the whole app.
 *
 * Saved on the account (ui_preferences) so they follow the person, and copied
 * into a cookie so the server paints the first frame with them (app/layout.tsx):
 * no flash of small text before the account arrives.
 */

export const A11Y_COOKIE = "fareeq_a11y";

export interface A11y {
  scale: number;
  contrast: boolean;
  calm: boolean;
}

export const A11Y_DEFAULT: A11y = { scale: 1, contrast: false, calm: false };
export const TEXT_SCALES = [1, 1.15, 1.3, 1.5];

/** "1.3_c_m": the scale, then c for high contrast and m for less motion. */
export function readA11y(value: string | undefined): A11y {
  if (!value) return A11Y_DEFAULT;
  const [scale, ...flags] = value.split("_");
  const n = Number(scale);
  return {
    scale: Number.isFinite(n) && n >= 1 && n <= 1.5 ? n : 1,
    contrast: flags.includes("c"),
    calm: flags.includes("m"),
  };
}

export function writeA11y(a: A11y): string {
  return [String(a.scale), a.contrast ? "c" : "", a.calm ? "m" : ""].filter(Boolean).join("_");
}

/** The attributes the <html> element carries for these settings. */
export function htmlA11y(a: A11y): { className: string; style: Record<string, string> } {
  return {
    className: [a.contrast ? "high-contrast" : "", a.calm ? "reduce-motion" : "", a.scale > 1 ? "text-large" : ""]
      .filter(Boolean)
      .join(" "),
    style: a.scale !== 1 ? { "--text-scale": String(a.scale) } : {},
  };
}

/** Applies the settings to the open page and remembers them for the next one. */
export function applyA11y(a: A11y) {
  const root = document.documentElement;
  root.classList.toggle("high-contrast", a.contrast);
  root.classList.toggle("reduce-motion", a.calm);
  // Larger text: a few layout allowances (globals.css), so 100% stays as designed.
  root.classList.toggle("text-large", a.scale > 1);
  if (a.scale !== 1) root.style.setProperty("--text-scale", String(a.scale));
  else root.style.removeProperty("--text-scale");
  document.cookie = `${A11Y_COOKIE}=${writeA11y(a)}; path=/; max-age=31536000; samesite=lax`;
}
