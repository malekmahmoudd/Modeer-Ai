import Link from "next/link";

import { AgentPortrait } from "@/components/art/AgentPortrait";
import type { Agent } from "@/types";

/**
 * An illustrated comic panel: bold ink border, a slanted name tab, the
 * specialist's portrait, and a readable caption bar. The tab and caption are
 * real HTML — no text is baked into artwork.
 */
export function AgentPanel({
  agent,
  index = 0,
  size = "md",
}: {
  agent: Agent;
  index?: number;
  size?: "md" | "lg";
}) {
  const tabPink = index % 2 === 1;

  return (
    <Link
      href={`/agents/${agent.id}`}
      className="group relative block overflow-hidden border-2 border-ink bg-paper-hi shadow-pop transition-transform duration-150 hover:-translate-y-[3px] focus-visible:-translate-y-[3px]"
    >
      {/* artwork */}
      <div
        className={`relative overflow-hidden ${
          size === "lg" ? "aspect-[4/5]" : "aspect-[5/6] sm:aspect-[4/5]"
        }`}
      >
        <AgentPortrait
          slug={agent.id}
          framing="panel"
          decorative
          className="absolute inset-0 h-full w-full transition-transform duration-200 group-hover:scale-[1.04]"
        />

        {/* slanted name tab — text upright */}
        <span
          className="name-tab absolute left-0 top-3 text-[14px] sm:text-[15px]"
          style={{ background: tabPink ? "var(--pink)" : "var(--sun)", color: tabPink ? "#fff" : "var(--ink)" }}
        >
          {agent.name.replace(/ (Agent|Assistant)$/, "")}
        </span>
      </div>

      {/* caption bar */}
      <div className="border-t-2 border-ink bg-paper-hi px-3 py-2.5">
        <p className="text-[13px] font-bold leading-tight text-ink">{agent.tagline}</p>
      </div>
    </Link>
  );
}
