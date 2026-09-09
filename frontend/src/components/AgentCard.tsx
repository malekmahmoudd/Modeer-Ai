import Link from "next/link";

import { AgentAvatar } from "@/components/AgentAvatar";
import { hexToRgba } from "@/lib/format";
import type { Agent } from "@/types";

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <Link
      href={`/agents/${agent.id}`}
      className="card group relative flex flex-col gap-3 overflow-hidden p-5 transition hover:-translate-y-0.5 hover:border-white/15"
    >
      <span
        className="pointer-events-none absolute inset-x-0 -top-16 h-32 opacity-0 blur-2xl transition group-hover:opacity-100"
        style={{ background: hexToRgba(agent.accent, 0.35) }}
      />
      <div className="flex items-center gap-3">
        <AgentAvatar icon={agent.icon} accent={agent.accent} size={44} />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{agent.name}</p>
          <p className="truncate text-xs text-white/45">{agent.role}</p>
        </div>
      </div>
      <p className="line-clamp-3 text-sm leading-relaxed text-white/55">
        {agent.description}
      </p>
      <div className="mt-auto flex items-center gap-2 pt-1">
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: agent.accent }}
        />
        <span className="text-[11px] font-medium uppercase tracking-wider text-white/35">
          {agent.is_assistant ? "Personal assistant" : "Specialist"}
        </span>
        <span className="ml-auto text-white/30 transition group-hover:translate-x-0.5 group-hover:text-white/60">
          →
        </span>
      </div>
    </Link>
  );
}
