"use client";

import { useCallback, useEffect, useState } from "react";

import { AgentAvatar } from "@/components/AgentAvatar";
import { MemoryRow } from "@/components/memory/MemoryRow";
import { EmptyState, SectionHeading, Spinner } from "@/components/ui/primitives";
import { apiFetch, useApi } from "@/lib/api";
import type { Agent, AgentMemory, SharedMemory } from "@/types";

interface AddForm {
  category: string;
  key: string;
  value: string;
}
const EMPTY: AddForm = { category: "general", key: "", value: "" };

export function MemoryManager() {
  const { data: agents } = useApi<Agent[]>("/agents");
  const specialists = (agents || []).filter((a) => !a.is_assistant);

  const {
    data: shared,
    loading: sharedLoading,
    refetch: refetchShared,
  } = useApi<SharedMemory[]>("/memory/shared");

  const [addingShared, setAddingShared] = useState<AddForm>(EMPTY);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [agentMem, setAgentMem] = useState<AgentMemory[]>([]);
  const [agentMemLoading, setAgentMemLoading] = useState(false);
  const [addingAgent, setAddingAgent] = useState<AddForm>(EMPTY);

  const loadAgentMem = useCallback(async (slug: string) => {
    if (!slug) return;
    setAgentMemLoading(true);
    try {
      setAgentMem(await apiFetch<AgentMemory[]>(`/memory/agent/${slug}`));
    } finally {
      setAgentMemLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedAgent) loadAgentMem(selectedAgent);
  }, [selectedAgent, loadAgentMem]);

  async function addShared(e: React.FormEvent) {
    e.preventDefault();
    if (!addingShared.key.trim() || !addingShared.value.trim()) return;
    await apiFetch("/memory/shared", {
      method: "POST",
      body: JSON.stringify({ ...addingShared, source: "user" }),
    });
    setAddingShared(EMPTY);
    refetchShared();
  }

  async function addAgent(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedAgent || !addingAgent.key.trim() || !addingAgent.value.trim()) return;
    await apiFetch("/memory/agent", {
      method: "POST",
      body: JSON.stringify({ ...addingAgent, agent_id: selectedAgent, source: "user" }),
    });
    setAddingAgent(EMPTY);
    loadAgentMem(selectedAgent);
  }

  const activeAgent = specialists.find((a) => a.id === selectedAgent);

  return (
    <div className="mx-auto max-w-4xl animate-fade-up">
      <div className="mb-8">
        <p className="text-sm text-white/40">Memory</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">
          What my AI team knows about me
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-white/50">
          Everything here is yours to edit or delete. Shared context is visible to
          every specialist. Specialist notes stay with one agent.
        </p>
      </div>

      {/* Shared */}
      <section className="mb-10">
        <SectionHeading
          title="Shared personal context"
          hint="Used by every agent on your team."
        />

        {sharedLoading && <Spinner />}
        {!sharedLoading && (shared || []).length === 0 && (
          <EmptyState title="Nothing shared yet">
            Talk to Modeer and mention something durable about yourself — your studies,
            your goals, where you&apos;re based — and it shows up here.
          </EmptyState>
        )}

        <div className="flex flex-col gap-2">
          {(shared || []).map((m) => (
            <MemoryRow
              key={m.id}
              memory={m}
              onSave={async (patch) => {
                await apiFetch(`/memory/shared/${m.id}`, {
                  method: "PATCH",
                  body: JSON.stringify(patch),
                });
                refetchShared();
              }}
              onDelete={async () => {
                await apiFetch(`/memory/shared/${m.id}`, { method: "DELETE" });
                refetchShared();
              }}
            />
          ))}
        </div>

        <form
          onSubmit={addShared}
          className="mt-3 flex flex-col gap-2 rounded-xl border border-dashed border-white/10 p-3.5 sm:flex-row"
        >
          <input
            className="input sm:w-40"
            placeholder="key (e.g. career_goal)"
            value={addingShared.key}
            onChange={(e) => setAddingShared({ ...addingShared, key: e.target.value })}
          />
          <input
            className="input flex-1"
            placeholder="value"
            value={addingShared.value}
            onChange={(e) => setAddingShared({ ...addingShared, value: e.target.value })}
          />
          <button type="submit" className="btn-primary shrink-0">
            Add
          </button>
        </form>
      </section>

      {/* Specialist notes */}
      <section>
        <SectionHeading
          title="Specialist notes"
          hint="Private to one agent."
          action={
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="input !w-auto !py-1.5 text-sm"
            >
              <option value="">Choose a specialist…</option>
              {specialists.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.icon} {a.name}
                </option>
              ))}
            </select>
          }
        />

        {!selectedAgent && (
          <EmptyState title="Pick a specialist">
            Choose an agent to see and manage the notes it keeps about you.
          </EmptyState>
        )}

        {selectedAgent && activeAgent && (
          <>
            <div className="mb-3 flex items-center gap-2.5">
              <AgentAvatar icon={activeAgent.icon} accent={activeAgent.accent} size={32} />
              <span className="text-sm text-white/70">{activeAgent.name}&apos;s notes</span>
            </div>

            {agentMemLoading && <Spinner />}
            {!agentMemLoading && agentMem.length === 0 && (
              <EmptyState title="No notes yet">
                As you chat with {activeAgent.name}, useful specialist details land here.
              </EmptyState>
            )}

            <div className="flex flex-col gap-2">
              {agentMem.map((m) => (
                <MemoryRow
                  key={m.id}
                  memory={m}
                  onSave={async (patch) => {
                    await apiFetch(`/memory/agent/${m.id}`, {
                      method: "PATCH",
                      body: JSON.stringify(patch),
                    });
                    loadAgentMem(selectedAgent);
                  }}
                  onDelete={async () => {
                    await apiFetch(`/memory/agent/${m.id}`, { method: "DELETE" });
                    loadAgentMem(selectedAgent);
                  }}
                />
              ))}
            </div>

            <form
              onSubmit={addAgent}
              className="mt-3 flex flex-col gap-2 rounded-xl border border-dashed border-white/10 p-3.5 sm:flex-row"
            >
              <input
                className="input sm:w-40"
                placeholder="key"
                value={addingAgent.key}
                onChange={(e) => setAddingAgent({ ...addingAgent, key: e.target.value })}
              />
              <input
                className="input flex-1"
                placeholder="value"
                value={addingAgent.value}
                onChange={(e) => setAddingAgent({ ...addingAgent, value: e.target.value })}
              />
              <button type="submit" className="btn-primary shrink-0">
                Add
              </button>
            </form>
          </>
        )}
      </section>
    </div>
  );
}
