"use client";

import { AgentPanel } from "@/components/AgentPanel";
import { useApi } from "@/lib/api";
import type { Agent } from "@/types";

export function AgentGrid({
  specialistsOnly = true,
  size = "md",
  featured = false,
}: {
  specialistsOnly?: boolean;
  size?: "md" | "lg";
  featured?: boolean;
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

  const allAgents = (data ?? []).filter((a) => (specialistsOnly ? !a.is_assistant : true));
  const agents = featured
    ? ["study", "career", "research", "writing"].flatMap((id) => allAgents.filter((a) => a.id === id))
    : allAgents;

  return (
    <div className={featured ? "sunshine-team-grid" : "team-directory grid grid-cols-2 gap-4 lg:grid-cols-3"}>
      {agents.map((agent, i) => (
        <AgentPanel key={agent.id} agent={agent} index={i} size={size} featured={featured} />
      ))}
    </div>
  );
}
