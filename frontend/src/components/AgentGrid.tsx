"use client";

import { AgentCard } from "@/components/AgentCard";
import { useApi } from "@/lib/api";
import type { Agent } from "@/types";

export function AgentGrid({ specialistsOnly = false }: { specialistsOnly?: boolean }) {
  const { data, loading, error } = useApi<Agent[]>("/agents");

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="card h-[72px] animate-pulse" />
        ))}
      </div>
    );
  }
  if (error) return <p className="text-[13px] text-red-300">{error}</p>;

  let agents = data || [];
  if (specialistsOnly) agents = agents.filter((a) => !a.is_assistant);

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {agents.map((agent, i) => (
        <div
          key={agent.id}
          className="anim-fade-up"
          style={{ animationDelay: `${Math.min(i * 32, 260)}ms` }}
        >
          <AgentCard agent={agent} />
        </div>
      ))}
    </div>
  );
}
