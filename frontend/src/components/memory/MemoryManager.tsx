"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { DocumentsPanel } from "@/components/memory/DocumentsPanel";
import { MemoryRow } from "@/components/memory/MemoryRow";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, PageHeader, SectionHead, Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch, useApi } from "@/lib/api";
import { categoryLabel } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
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
  const { t } = usePrefs();
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
          setErr(t("memory.needBoth"));
          return;
        }
        setBusy(true);
        setErr(null);
        try {
          await onAdd(v);
          setV(EMPTY);
          setOpen(false);
        } catch (ex) {
          setErr(ex instanceof Error ? ex.message : t("memory.saveError"));
        } finally {
          setBusy(false);
        }
      }}
      className="mt-3 border-2 border-dashed border-ink bg-paper-hi p-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          className="field sm:w-52"
          dir="auto"
          placeholder={t("memory.labelPlaceholder")}
          aria-label={t("memory.label")}
          value={v.key}
          onChange={(e) => setV({ ...v, key: e.target.value })}
        />
        <input
          className="field flex-1"
          dir="auto"
          placeholder={t("memory.valuePlaceholder")}
          aria-label={t("memory.value")}
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
          {busy ? t("common.saving") : t("common.save")}
        </button>
        <button
          type="button"
          onClick={() => {
            setOpen(false);
            setErr(null);
          }}
          className="btn !min-h-[40px] !text-[13.5px]"
        >
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

export function MemoryManager() {
  const { agents } = useAgents();
  const { t } = usePrefs();
  const agentName = useAgentName();
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
      if (request === memoryRequest.current) setAgentError(error instanceof Error ? error.message : t("memory.notesError"));
    } finally {
      if (request === memoryRequest.current) setAgentLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (agentId) loadAgent(agentId);
  }, [agentId, loadAgent]);

  const sharedGroups = useMemo(() => groupByCategory(shared || []), [shared]);
  const activeAgent = specialists.find((a) => a.id === agentId);

  return (
    <div className="anim-fade journal-page memory-page">
      <PageHeader
        eyebrow={t("memory.eyebrow")}
        title={t("memory.title")}
        lede={t("memory.lede")}
      />

      {/* ---------- shared ---------- */}
      <section className="memory-shared">
        <SectionHead title={t("memory.shared")} />
        <p className="-mt-2 mb-5 text-[14px] font-semibold text-ink-soft">{t("memory.sharedHelp")}</p>

        {loading && <Spinner />}
        {error && (
          <p role="alert" className="border-2 border-ink bg-pink-pale px-3 py-2 text-[14px] font-semibold">
            {t("memory.loadError", { error })}
          </p>
        )}

        {!loading && !error && (shared ?? []).length === 0 && (
          <EmptyState title={t("memory.nothingShared")}>{t("memory.nothingSharedHelp")}</EmptyState>
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
                    scope="shared"
                    onChanged={refetch}
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
          label={t("memory.addSomething")}
          onAdd={async (v) => {
            await apiFetch("/memory/shared", {
              method: "POST",
              body: JSON.stringify({ ...v, category: "general", source: "user" }),
            });
            refetch();
          }}
        />
      </section>

      {/* ---------- files ---------- */}
      <DocumentsPanel />

      {/* ---------- specialist ---------- */}
      <section className="memory-private">
        <SectionHead title={t("memory.private")} />
        <p className="-mt-2 mb-5 text-[14px] font-semibold text-ink-soft">{t("memory.privateHelp")}</p>

        <ul className="mb-6 flex flex-wrap gap-2.5" role="list">
          {specialists.map((a) => {
            const on = a.id === agentId;
            return (
              <li key={a.id}>
                <button
                  onClick={() => setAgentId(on ? "" : a.id)}
                  aria-pressed={on}
                  className={`flex items-center gap-2 border-2 border-ink py-1.5 pe-3 ps-1.5 text-[13px] font-bold transition ${
                    on ? "bg-pink text-ink shadow-pop-xs" : "bg-paper-hi text-ink hover:bg-sun-pale"
                  }`}
                >
                  <AgentBadge slug={a.id} size={30} />
                  {agentName(a)}
                </button>
              </li>
            );
          })}
        </ul>

        {!agentId && (
          <EmptyState title={t("memory.pick")}>{t("memory.pickHelp")}</EmptyState>
        )}

        {agentId && activeAgent && (
          <>
            {agentLoading && <Spinner />}

            {agentError && <p role="alert">{agentError}</p>}
            {!agentLoading && !agentError && agentMem.length === 0 && (
              <EmptyState title={t("memory.noNotes")}>{t("memory.noNotesHelp", { name: agentName(activeAgent) })}</EmptyState>
            )}

            {agentMem.length > 0 && (
              <div className="border-2 border-ink bg-paper-hi shadow-pop-xs">
                <p className="border-b-2 border-ink bg-sun px-3 py-1.5 text-[11.5px] font-black uppercase tracking-[0.13em] text-ink">
                  {t("memory.privateNotes", { name: agentName(activeAgent) })}
                </p>
                <ul>
                  {agentMem.map((m) => (
                    <li key={m.id} className="border-b border-ink/20 last:border-b-0">
                      <MemoryRow
                        memory={m}
                        scope="agent"
                        onChanged={() => loadAgent(agentId)}
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
              label={t("memory.addNote", { name: agentName(activeAgent) })}
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
