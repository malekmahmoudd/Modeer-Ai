"use client";

import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { apiFetch } from "@/lib/api";
import { humanizeKey, relativeTime } from "@/lib/format";
import type { MemorySource } from "@/types";

export interface EditableMemory {
  id: string;
  category: string;
  key: string;
  value: string;
  source: string;
  sensitive: boolean;
}

export function MemoryRow({
  memory,
  scope,
  onSave,
  onDelete,
  onChanged,
}: {
  memory: EditableMemory;
  /** Which layer it lives in, for "why it knows" and undo. */
  scope: "shared" | "agent";
  onSave: (patch: { key: string; value: string }) => Promise<void>;
  onDelete: () => Promise<void>;
  /** Called after an undo changed the value. */
  onChanged: () => void;
}) {
  const [why, setWhy] = useState<MemorySource | null>(null);
  const [whyOpen, setWhyOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [draft, setDraft] = useState({ key: memory.key, value: memory.value });

  async function save() {
    if (!draft.key.trim() || !draft.value.trim()) {
      setErr("Both fields are needed.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await onSave(draft);
      setEditing(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleWhy() {
    if (whyOpen) {
      setWhyOpen(false);
      return;
    }
    setErr(null);
    try {
      setWhy(await apiFetch<MemorySource>(`/memory/${scope}/${memory.id}/source`));
      setWhyOpen(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't load where this came from.");
    }
  }

  async function undo() {
    setBusy(true);
    setErr(null);
    try {
      await apiFetch(`/memory/${scope}/${memory.id}/undo`, { method: "POST" });
      setWhyOpen(false);
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't undo.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setErr(null);
    try {
      await onDelete();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't delete.");
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <div className="bg-sun-pale/60 p-3">
        <label className="eyebrow mb-1 block" htmlFor={`k-${memory.id}`}>
          Label
        </label>
        <input
          id={`k-${memory.id}`}
          className="field mb-2"
          value={draft.key}
          onChange={(e) => setDraft({ ...draft, key: e.target.value })}
        />
        <label className="eyebrow mb-1 block" htmlFor={`v-${memory.id}`}>
          What the team knows
        </label>
        <textarea
          id={`v-${memory.id}`}
          className="field min-h-[76px]"
          value={draft.value}
          onChange={(e) => setDraft({ ...draft, value: e.target.value })}
        />
        {err && (
          <p role="alert" className="mt-2 text-[13px] font-bold text-pink-deep">
            {err}
          </p>
        )}
        <div className="mt-3 flex gap-2">
          <button onClick={save} disabled={busy} className="btn btn-pink !min-h-[40px] !text-[13px]">
            {busy ? "Saving…" : "Save"}
          </button>
          <button
            onClick={() => {
              setDraft({ key: memory.key, value: memory.value });
              setEditing(false);
              setErr(null);
            }}
            className="btn !min-h-[40px] !text-[13px]"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-3 px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <p className="text-[14.5px] font-semibold leading-snug text-ink">{memory.value}</p>
          <p className="mt-0.5 text-[11.5px] font-bold uppercase tracking-wide text-ink-faint">
            {humanizeKey(memory.key)}
            {memory.sensitive && (
              <span className="ml-2 border border-ink bg-pink-pale px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-ink">
                sensitive
              </span>
            )}
          </p>
          {err && (
            <p role="alert" className="mt-1 text-[12.5px] font-bold text-pink-deep">
              {err}
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-1.5">
          <button
            onClick={toggleWhy}
            aria-expanded={whyOpen}
            className="btn-icon !h-11 !w-11"
            aria-label={`Why the team knows ${humanizeKey(memory.key)}`}
          >
            <Icon name="history" size={17} />
          </button>
          <button
            onClick={() => setEditing(true)}
            className="btn-icon !h-11 !w-11"
            aria-label={`Edit ${humanizeKey(memory.key)}`}
          >
            <Icon name="pencil" size={17} />
          </button>
          <button
            onClick={remove}
            disabled={busy}
            className="btn-icon !h-11 !w-11 hover:!bg-pink hover:!text-ink"
            aria-label={`Delete ${humanizeKey(memory.key)}`}
          >
            <Icon name="trash" size={17} />
          </button>
        </div>
      </div>
      {whyOpen && why && (
        <div className="mx-3 mb-2.5 border-2 border-ink bg-sun-pale/60 px-3 py-2.5 text-[13.5px] leading-relaxed text-ink">
          {why.saved_by_you ? (
            <p className="font-semibold">You saved or edited this yourself.</p>
          ) : why.learned_from ? (
            <p>
              <span className="font-semibold">Learned from what you said</span>
              {why.learned_from.said_at && ` ${relativeTime(why.learned_from.said_at)}`}:{" "}
              <q className="italic">{why.learned_from.excerpt}</q>
            </p>
          ) : (
            <p className="font-semibold">Learned automatically; the message it came from is no longer there.</p>
          )}
          {why.history.length > 0 && (
            <>
              <p className="mt-2 font-semibold">Earlier values</p>
              <ul className="list-disc pl-5">
                {why.history.slice().reverse().map((h, i) => (
                  <li key={i}>
                    {h.value} <span className="text-ink-soft">({relativeTime(h.replaced_at)})</span>
                  </li>
                ))}
              </ul>
              <button onClick={undo} disabled={busy} className="btn mt-2.5 !min-h-[40px] !text-[13px]">
                Undo the last change
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
