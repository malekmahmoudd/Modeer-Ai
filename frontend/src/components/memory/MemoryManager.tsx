"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentAvatar } from "@/components/AgentAvatar";
import { MemoryRow } from "@/components/memory/MemoryRow";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, PageHeader, Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch, useApi } from "@/lib/api";
import { accentStyle, categoryLabel } from "@/lib/format";
import type { AgentMemory, SharedMemory } from "@/types";

const EMPTY = { key: "", value: "" };

function groupByCategory<T extends { category: string }>(rows: T[]): [string, T[]][] {
  const map = new Map<string, T[]>();
  for (const r of rows) {
    if (!map.has(r.category)) map.set(r.category, []);
    map.get(r.category)!.push(r);
  }
  return [...map.entries()];
}

function AddForm({ onAdd }: { onAdd: (v: { key: string; value: string }) => Promise<void> }) {
  const [v, setV] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="btn-ghost mt-1 h-9 text-[12.5px]"
      >
        <Icon name="plus" size={14} /> Add something
      </button>
    );
  }
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!v.key.trim() || !v.value.trim()) return;
        await onAdd(v);
        setV(EMPTY);
        setOpen(false);
      }}
      className="mt-2 flex flex-col gap-2 rounded-[12px] border border-dashed border-line-strong p-3 sm:flex-row"
    >
      <input
        className="field sm:w-44"
        placeholder="label (e.g. Career goal)"
        value={v.key}
        onChange={(e) => setV({ ...v, key: e.target.value })}
      />
      <input
        className="field flex-1"
        placeholder="what should the team know?"
        value={v.value}
        onChange={(e) => setV({ ...v, value: e.target.value })}
      />
      <button type="submit" className="btn-primary shrink-0">
        Save
      </button>
    </form>
  );
}

export function MemoryManager() {
  const { agents } = useAgents();
  const specialists = agents.filter((a) => !a.is_assistant);

  const { data: shared, loading, refetch } = useApi<SharedMemory[]>("/memory/shared");
  const [agentId, setAgentId] = useState("");
  const [agentMem, setAgentMem] = useState<AgentMemory[]>([]);
  const [agentLoading, setAgentLoading] = useState(false);

  const loadAgent = useCallback(async (slug: string) => {
    if (!slug) return;
    setAgentLoading(true);
    try {
      setAgentMem(await apiFetch<AgentMemory[]>(`/memory/agent/${slug}`));
    } finally {
      setAgentLoading(false);
    }
  }, []);

  useEffect(() => {
    if (agentId) loadAgent(agentId);
  }, [agentId, loadAgent]);

  const sharedGroups = useMemo(() => groupByCategory(shared || []), [shared]);
  const activeAgent = specialists.find((a) => a.id === agentId);

  return (
    <div className="anim-fade-up max-w-2xl">
      <PageHeader
        eyebrow="Memory"
        title="What my AI team knows about me"
        lede="Everything here is yours — inspect, edit or delete anything. Modeer never saves sensitive details (health, finances, IDs) on its own."
      />

      {/* Shared */}
      <section className="mb-12">
        <h2 className="mb-1 text-[15px] font-semibold tracking-tight text-white">
          Shared with your team
        </h2>
        <p className="mb-4 text-[12.5px] text-content-dim">Every specialist can see these.</p>

        {loading && <Spinner />}
        {!loading && (shared || []).length === 0 && (
          <EmptyState title="Nothing shared yet">
            Tell Modeer something durable about yourself and it shows up here.
          </EmptyState>
        )}

        {sharedGroups.map(([category, rows]) => (
          <div key={category} className="card mb-2.5 p-2">
            <p className="px-2 pb-1 pt-0.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-content-faint">
              {categoryLabel(category)}
            </p>
            {rows.map((m) => (
              <MemoryRow
                key={m.id}
                memory={m}
                onSave={async (patch) => {
                  await apiFetch(`/memory/shared/${m.id}`, {
                    method: "PATCH",
                    body: JSON.stringify(patch),
                  });
                  refetch();
                }}
                onDelete={async () => {
                  await apiFetch(`/memory/shared/${m.id}`, { method: "DELETE" });
                  refetch();
                }}
              />
            ))}
          </div>
        ))}

        <AddForm
          onAdd={async (v) => {
            await apiFetch("/memory/shared", {
              method: "POST",
              body: JSON.stringify({ ...v, category: "general", source: "user" }),
            });
            refetch();
          }}
        />
      </section>

      {/* Specialist */}
      <section>
        <h2 className="mb-1 text-[15px] font-semibold tracking-tight text-white">
          Known by specific agents
        </h2>
        <p className="mb-4 text-[12.5px] text-content-dim">
          Private notes a specialist keeps — only that agent sees them.
        </p>

        <div className="mb-4 flex flex-wrap gap-1.5">
          {specialists.map((a) => (
            <button
              key={a.id}
              onClick={() => setAgentId(a.id === agentId ? "" : a.id)}
              className="tag transition"
              style={
                a.id === agentId
                  ? { ...accentStyle(a.accent), borderColor: a.accent, color: "#fff" }
                  : undefined
              }
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: a.accent }} />
              {a.name.replace(" Agent", "")}
            </button>
          ))}
        </div>

        {!agentId && (
          <EmptyState title="Pick a specialist">
            Choose an agent above to see and manage the notes it keeps about you.
          </EmptyState>
        )}

        {agentId && activeAgent && (
          <div style={accentStyle(activeAgent.accent)}>
            <div className="mb-3 flex items-center gap-2.5">
              <AgentAvatar icon={activeAgent.icon} accent={activeAgent.accent} size={28} />
              <span className="text-[13px] text-content-dim">
                {activeAgent.name}&apos;s private notes
              </span>
            </div>

            {agentLoading && <Spinner />}
            {!agentLoading && agentMem.length === 0 && (
              <EmptyState title="No notes yet">
                As you chat with {activeAgent.name}, useful specialist details land here.
              </EmptyState>
            )}

            {agentMem.length > 0 && (
              <div className="card p-2.5">
                {agentMem.map((m) => (
                  <MemoryRow
                    key={m.id}
                    memory={m}
                    onSave={async (patch) => {
                      await apiFetch(`/memory/agent/${m.id}`, {
                        method: "PATCH",
                        body: JSON.stringify(patch),
                      });
                      loadAgent(agentId);
                    }}
                    onDelete={async () => {
                      await apiFetch(`/memory/agent/${m.id}`, { method: "DELETE" });
                      loadAgent(agentId);
                    }}
                  />
                ))}
              </div>
            )}

            <AddForm
              onAdd={async (v) => {
                await apiFetch("/memory/agent", {
                  method: "POST",
                  body: JSON.stringify({
                    ...v,
                    agent_id: agentId,
                    category: "general",
                    source: "user",
                  }),
                });
                loadAgent(agentId);
              }}
            />
          </div>
        )}
      </section>
    </div>
  );
}
