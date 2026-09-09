/**
 * Slug -> artwork. Renders the finished `image` when a character has one,
 * otherwise the generated SVG portrait. Layout never needs to know which.
 */
import { Portrait, type Framing } from "@/components/art/Portrait";
import { characterFor } from "@/lib/characters";

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

  if (character.image) {
    return (
      // Character art is an arbitrary replaceable asset; plain <img> keeps the
      // swap a one-line change in lib/characters.ts.
      /* eslint-disable-next-line @next/next/no-img-element */
      <img
        src={character.image}
        alt={decorative ? "" : alt}
        aria-hidden={decorative || undefined}
        className={className}
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
