"use client";

import { AgentCard } from "@/components/AgentCard";
import { useApi } from "@/lib/api";
import type { Agent } from "@/types";

export function AgentGrid({
  assistantsOnly = false,
  specialistsOnly = false,
}: {
  assistantsOnly?: boolean;
  specialistsOnly?: boolean;
}) {
  const { data, loading, error } = useApi<Agent[]>("/agents");

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="card h-44 animate-pulse bg-white/[0.02]" />
        ))}
      </div>
    );
  }
  if (error) return <p className="text-sm text-red-300">{error}</p>;

  let agents = data || [];
  if (assistantsOnly) agents = agents.filter((a) => a.is_assistant);
  if (specialistsOnly) agents = agents.filter((a) => !a.is_assistant);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} />
      ))}
    </div>
  );
}
