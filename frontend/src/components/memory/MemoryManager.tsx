"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { MemoryRow } from "@/components/memory/MemoryRow";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, PageHeader, SectionHead, Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch, useApi } from "@/lib/api";
import { categoryLabel } from "@/lib/format";
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

function AddForm({
  onAdd,
  label,
}: {
  onAdd: (v: { key: string; value: string }) => Promise<void>;
  label: string;
}) {
  const [v, setV] = useState(EMPTY);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="btn mt-3 !min-h-[42px] !text-[13.5px]">
        <Icon name="plus" size={16} /> {label}
      </button>
    );
  }

  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        if (!v.key.trim() || !v.value.trim()) {
          setErr("Give it a short label and a value.");
          return;
        }
        setBusy(true);
        setErr(null);
        try {
          await onAdd(v);
          setV(EMPTY);
          setOpen(false);
        } catch (ex) {
          setErr(ex instanceof Error ? ex.message : "Couldn't save that.");
        } finally {
          setBusy(false);
        }
      }}
      className="mt-3 border-2 border-dashed border-ink bg-paper-hi p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          className="field sm:w-52"
          placeholder="Label (e.g. Career goal)"
          aria-label="Label"
          value={v.key}
          onChange={(e) => setV({ ...v, key: e.target.value })}
        />
        <input
          className="field flex-1"
          placeholder="What should the team know?"
          aria-label="Value"
          value={v.value}
          onChange={(e) => setV({ ...v, value: e.target.value })}
        />
      </div>
      {err && (
        <p role="alert" className="mt-2 text-[13px] font-bold text-pink-deep">
          {err}
        </p>
      )}
      <div className="mt-3 flex gap-2">
        <button type="submit" disabled={busy} className="btn btn-pink !min-h-[40px] !text-[13.5px]">
          {busy ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            setErr(null);
          }}
          className="btn !min-h-[40px] !text-[13.5px]"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export function MemoryManager() {
  const { agents } = useAgents();
  const specialists = agents.filter((a) => !a.is_assistant);

  const { data: shared, loading, error, refetch } = useApi<SharedMemory[]>("/memory/shared");
  const [agentId, setAgentId] = useState("");
  const [agentMem, setAgentMem] = useState<AgentMemory[]>([]);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const memoryRequest = useRef(0);

  const loadAgent = useCallback(async (slug: string) => {
    if (!slug) return;
    const request = ++memoryRequest.current;
    setAgentLoading(true);
    setAgentError(null);
    setAgentMem([]);
    try {
      const rows = await apiFetch<AgentMemory[]>(`/memory/agent/${slug}`);
      if (request === memoryRequest.current) setAgentMem(rows);
    } catch (error) {
      if (request === memoryRequest.current) setAgentError(error instanceof Error ? error.message : "Could not load notes.");
    } finally {
      if (request === memoryRequest.current) setAgentLoading(false);
    }
  }, []);

  useEffect(() => {
    if (agentId) loadAgent(agentId);
  }, [agentId, loadAgent]);

  const sharedGroups = useMemo(() => groupByCategory(shared || []), [shared]);
  const activeAgent = specialists.find((a) => a.id === agentId);

  return (
    <div className="anim-fade journal-page memory-page">
      <PageHeader
        eyebrow="Your memory book"
        title="A little more you."
        lede="Everything here is yours — inspect, edit or delete anything. Modeer never saves sensitive details (health, finances, IDs) on its own."
      />

      {/* ---------- shared ---------- */}
      <section className="memory-shared">
        <SectionHead title="Shared with your team" />
        <p className="-mt-2 mb-5 text-[14px] font-semibold text-ink-soft">
          Every specialist can see these.
        </p>

        {loading && <Spinner />}
        {error && (
          <p role="alert" className="border-2 border-ink bg-pink-pale px-3 py-2 text-[14px] font-semibold">
            Couldn&apos;t load your memory: {error}
          </p>
        )}

        {!loading && !error && (shared ?? []).length === 0 && (
          <EmptyState title="Nothing shared yet">
            Tell Modeer something lasting about yourself and it shows up here.
          </EmptyState>
        )}

        {sharedGroups.map(([category, rows]) => (
          <div key={category} className="memory-category mb-4 border-2 border-ink bg-paper-hi shadow-pop-xs">
            <p className="border-b-2 border-ink bg-sun px-3 py-1.5 text-[11.5px] font-black uppercase tracking-[0.13em] text-ink">
              {categoryLabel(category)}
            </p>
            <ul>
              {rows.map((m) => (
                <li key={m.id} className="border-b border-ink/20 last:border-b-0">
                  <MemoryRow
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
                </li>
              ))}
            </ul>
          </div>
        ))}

        <AddForm
          label="Add something"
          onAdd={async (v) => {
            await apiFetch("/memory/shared", {
              method: "POST",
              body: JSON.stringify({ ...v, category: "general", source: "user" }),
            });
            refetch();
          }}
        />
      </section>

      {/* ---------- specialist ---------- */}
      <section className="memory-private">
        <SectionHead title="Known by one specialist" />
        <p className="-mt-2 mb-5 text-[14px] font-semibold text-ink-soft">
          Private notes a specialist keeps — only that agent sees them.
        </p>

        <ul className="mb-6 flex flex-wrap gap-2.5" role="list">
          {specialists.map((a) => {
            const on = a.id === agentId;
            return (
              <li key={a.id}>
                <button
                  onClick={() => setAgentId(on ? "" : a.id)}
                  aria-pressed={on}
                  className={`flex items-center gap-2 border-2 border-ink py-1.5 pl-1.5 pr-3 text-[13px] font-bold transition ${
                    on ? "bg-pink text-white shadow-pop-xs" : "bg-paper-hi text-ink hover:bg-sun-pale"
                  }`}
                >
                  <AgentBadge slug={a.id} size={30} />
                  {a.name.replace(/ (Agent|Assistant)$/, "")}
                </button>
              </li>
            );
          })}
        </ul>

        {!agentId && (
          <EmptyState title="Pick a specialist">
            Choose an agent above to see and manage the notes it keeps about you.
          </EmptyState>
        )}

        {agentId && activeAgent && (
          <>
            {agentLoading && <Spinner />}

            {agentError && <p role="alert">{agentError}</p>}
            {!agentLoading && !agentError && agentMem.length === 0 && (
              <EmptyState title="No notes yet">
                As you chat with {activeAgent.name}, useful specialist details land here.
              </EmptyState>
            )}

            {agentMem.length > 0 && (
              <div className="border-2 border-ink bg-paper-hi shadow-pop-xs">
                <p className="border-b-2 border-ink bg-sun px-3 py-1.5 text-[11.5px] font-black uppercase tracking-[0.13em] text-ink">
                  {activeAgent.name}&apos;s private notes
                </p>
                <ul>
                  {agentMem.map((m) => (
                    <li key={m.id} className="border-b border-ink/20 last:border-b-0">
                      <MemoryRow
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
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <AddForm
              label={`Add a note for ${activeAgent.name.replace(/ (Agent|Assistant)$/, "")}`}
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
          </>
        )}
      </section>
    </div>
  );
}
