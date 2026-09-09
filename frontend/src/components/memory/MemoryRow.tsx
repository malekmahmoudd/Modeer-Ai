"use client";

import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { humanizeKey } from "@/lib/format";

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
  onSave,
  onDelete,
}: {
  memory: EditableMemory;
  onSave: (patch: { key: string; value: string }) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
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
          onClick={() => setEditing(true)}
          className="btn-icon !h-11 !w-11"
          aria-label={`Edit ${humanizeKey(memory.key)}`}
        >
          <Icon name="pencil" size={17} />
        </button>
        <button
          onClick={remove}
          disabled={busy}
          className="btn-icon !h-11 !w-11 hover:!bg-pink hover:!text-white"
          aria-label={`Delete ${humanizeKey(memory.key)}`}
        >
          <Icon name="trash" size={17} />
        </button>
      </div>
    </div>
  );
}
