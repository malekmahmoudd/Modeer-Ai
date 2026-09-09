import { hexToRgba } from "@/lib/format";

export function AgentAvatar({
  icon,
  accent,
  size = 40,
  ring = true,
}: {
  icon: string;
  accent: string;
  size?: number;
  ring?: boolean;
}) {
  return (
    <span
      className="grid shrink-0 place-items-center rounded-xl"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.5,
        background: `linear-gradient(140deg, ${hexToRgba(accent, 0.32)}, ${hexToRgba(
          accent,
          0.08,
        )})`,
        boxShadow: ring ? `inset 0 0 0 1px ${hexToRgba(accent, 0.4)}` : undefined,
      }}
    >
      {icon}
    </span>
  );
}
