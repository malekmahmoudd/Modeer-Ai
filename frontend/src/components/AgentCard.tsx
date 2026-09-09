import Link from "next/link";

import { AgentAvatar } from "@/components/AgentAvatar";
import { Icon } from "@/components/ui/Icon";
import { hexToRgba } from "@/lib/format";
import type { Agent } from "@/types";

/** A team-member card: reads in under a second — who, what, why open it. */
export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <Link
      href={`/agents/${agent.id}`}
      className="lift card group relative flex items-center gap-3.5 overflow-hidden p-4"
    >
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-[3px]"
        style={{ background: agent.accent }}
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -left-6 top-1/2 h-16 w-16 -translate-y-1/2 rounded-full opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-60"
        style={{ background: hexToRgba(agent.accent, 0.5) }}
      />
      <AgentAvatar icon={agent.icon} accent={agent.accent} size={40} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14px] font-semibold tracking-tight text-white">
          {agent.name}
        </span>
        <span className="block truncate text-[12.5px] text-content-dim">{agent.tagline}</span>
      </span>
      <Icon
        name="arrow-right"
        size={16}
        className="shrink-0 text-content-faint transition group-hover:translate-x-0.5 group-hover:text-content-dim"
      />
    </Link>
  );
}
