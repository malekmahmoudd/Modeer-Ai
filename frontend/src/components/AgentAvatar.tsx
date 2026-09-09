import { hexToRgba } from "@/lib/format";

/** Restrained agent mark: a soft accent-tinted tile with the agent's glyph. */
export function AgentAvatar({
  icon,
  accent,
  size = 38,
}: {
  icon: string;
  accent: string;
  size?: number;
}) {
  return (
    <span
      className="grid shrink-0 place-items-center rounded-[10px]"
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.46),
        lineHeight: 1,
        background: hexToRgba(accent, 0.12),
        boxShadow: `inset 0 0 0 1px ${hexToRgba(accent, 0.22)}`,
      }}
    >
      <span style={{ filter: "saturate(1.05)" }}>{icon}</span>
    </span>
  );
}
