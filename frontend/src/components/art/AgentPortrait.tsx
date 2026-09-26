/**
 * Slug -> artwork. Renders the finished `image` when a character has one,
 * otherwise the generated SVG portrait. Layout never needs to know which.
 */
"use client";

import { Portrait, type Framing } from "@/components/art/Portrait";
import { characterFor } from "@/lib/characters";
import { usePrefs } from "@/lib/i18n";

export function AgentPortrait({
  slug,
  framing = "bust",
  className = "",
  decorative = false,
  altOverride,
  transparent = false,
  fit = "cover",
}: {
  slug: string;
  framing?: Framing;
  className?: string;
  decorative?: boolean;
  altOverride?: string;
  transparent?: boolean;
  fit?: "cover" | "contain";
}) {
  const character = characterFor(slug);
  const alt = altOverride ?? character.alt;
  // Data saver: the drawn SVG portrait (in the page already) instead of a
  // downloaded illustration.
  const { dataSaver } = usePrefs();

  if (character.image && !dataSaver) {
    return (
      // Character art is an arbitrary replaceable asset; plain <img> keeps the
      // swap a one-line change in lib/characters.ts.
      /* eslint-disable-next-line @next/next/no-img-element */
      <img
        src={character.image}
        alt={decorative ? "" : alt}
        aria-hidden={decorative || undefined}
        className={className}
        style={{ objectFit: fit, objectPosition: character.imagePosition ?? (framing === "head" ? "50% 25%" : "50% 38%"), ...(framing === "head" ? { transform: "scale(1.8)", transformOrigin: character.imagePosition ?? "50% 25%" } : {}) }}
      />
    );
  }

  return (
    <Portrait
      spec={character.art}
      alt={alt}
      framing={framing}
      className={className}
      decorative={decorative}
      transparent={transparent}
      fit={fit}
    />
  );
}

/**
 * Small circular head crop — message rows, memory pickers, compact headers.
 */
export function AgentBadge({
  slug,
  size = 40,
  className = "",
}: {
  slug: string;
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={`inline-block shrink-0 overflow-hidden rounded-full border-2 border-ink bg-sun-pale ${className}`}
      style={{ width: size, height: size }}
    >
      <AgentPortrait slug={slug} framing="head" decorative className="h-full w-full" />
    </span>
  );
}
