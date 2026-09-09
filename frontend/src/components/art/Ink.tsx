/**
 * Sunshine & Ink — background geometry and ink flourishes.
 * All CSS/SVG so it stays sharp and responsive; nothing here overflows its
 * container (every stage clips), and none of it is interactive.
 */

/** Broad diagonal cream / yellow / pink fields behind the hero. */
export function HeroDiagonals({ className = "" }: { className?: string }) {
  return (
    <div className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`} aria-hidden>
      <svg
        viewBox="0 0 1200 640"
        preserveAspectRatio="none"
        className="h-full w-full"
      >
        <defs>
          <pattern id="heroDots" width="14" height="14" patternUnits="userSpaceOnUse">
            <circle cx="3" cy="3" r="2.1" fill="var(--ink)" opacity="0.13" />
          </pattern>
        </defs>

        <rect width="1200" height="640" fill="var(--paper)" />

        {/* upper-left yellow wedge */}
        <path d="M-120,-40 L370,-40 L40,430 L-120,430 Z" fill="var(--sun)" />
        {/* broad yellow field behind the portrait */}
        <path d="M520,-40 L1010,-40 L700,680 L210,680 Z" fill="var(--sun)" />
        {/* vivid pink diagonal, right */}
        <path d="M1000,-40 L1330,-40 L1030,680 L700,680 Z" fill="var(--pink)" />
        {/* pink sliver, lower left — balances the composition */}
        <path d="M-120,486 L128,486 L26,680 L-120,680 Z" fill="var(--pink)" />

        {/* print texture over the colour fields only */}
        <path d="M540,-40 L1000,-40 L700,680 L240,680 Z" fill="url(#heroDots)" />
        <path d="M-120,-40 L360,-40 L40,420 L-120,420 Z" fill="url(#heroDots)" />
      </svg>
    </div>
  );
}

/** Thin ink rule with a heavier cap — section dividers. */
export function InkRule({ className = "" }: { className?: string }) {
  return <hr className={`rule ${className}`} aria-hidden />;
}

/** A short hand-lettered margin note. Decorative only — never load-bearing. */
export function Scribble({
  children,
  className = "",
  underline = false,
  tone = "ink",
}: {
  children: React.ReactNode;
  className?: string;
  underline?: boolean;
  tone?: "ink" | "pink";
}) {
  return (
    <span
      aria-hidden
      className={`hand pointer-events-none select-none text-[17px] uppercase leading-tight sm:text-[19px] ${
        tone === "pink" ? "text-pink-deep" : "text-ink"
      } ${className}`}
    >
      {children}
      {underline && (
        <svg viewBox="0 0 120 10" className="mt-0.5 block h-[7px] w-[86px]" preserveAspectRatio="none">
          <path
            d="M2,7 C28,2 76,2 118,5"
            fill="none"
            stroke="var(--pink)"
            strokeWidth="4"
            strokeLinecap="round"
          />
        </svg>
      )}
    </span>
  );
}

/** Halftone corner flourish for panels and empty states. */
export function Halftone({
  className = "",
  colour = "var(--ink)",
}: {
  className?: string;
  colour?: string;
}) {
  return (
    <svg className={className} viewBox="0 0 120 120" aria-hidden>
      <defs>
        <radialGradient id="htFade">
          <stop offset="0%" stopColor="#fff" stopOpacity="1" />
          <stop offset="100%" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <mask id="htMask">
          <rect width="120" height="120" fill="url(#htFade)" />
        </mask>
        <pattern id="htDots" width="10" height="10" patternUnits="userSpaceOnUse">
          <circle cx="2.6" cy="2.6" r="2.1" fill={colour} />
        </pattern>
      </defs>
      <rect width="120" height="120" fill="url(#htDots)" mask="url(#htMask)" opacity="0.5" />
    </svg>
  );
}
