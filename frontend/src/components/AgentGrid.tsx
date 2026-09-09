"use client";

import { AgentPanel } from "@/components/AgentPanel";
import { useApi } from "@/lib/api";
import type { Agent } from "@/types";

export function AgentGrid({
  specialistsOnly = true,
  size = "md",
}: {
  specialistsOnly?: boolean;
  size?: "md" | "lg";
}) {
  const { data, loading, error } = useApi<Agent[]>("/agents");

  if (loading) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="aspect-[4/5] animate-pulse border-2 border-ink bg-paper-lo shadow-pop"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <p
        role="alert"
        className="border-2 border-ink bg-pink-pale px-4 py-3 text-[14px] font-semibold text-ink"
      >
        Couldn&apos;t load your team: {error}
      </p>
    );
  }

  const agents = (data ?? []).filter((a) => (specialistsOnly ? !a.is_assistant : true));

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {agents.map((agent, i) => (
        <AgentPanel key={agent.id} agent={agent} index={i} size={size} />
      ))}
    </div>
  );
}
