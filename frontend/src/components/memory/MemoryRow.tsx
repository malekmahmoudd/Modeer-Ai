"use client";

import { useState } from "react";

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
  onSave: (patch: { category: string; key: string; value: string }) => Promise<void>;
  onDelete: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState({
    category: memory.category,
    key: memory.key,
    value: memory.value,
  });

  async function save() {
    setBusy(true);
    try {
      await onSave(draft);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3.5 sm:flex-row sm:items-start">
      <div className="w-full sm:w-44 sm:shrink-0">
        {editing ? (
          <input
            className="input !py-1.5 text-xs"
            value={draft.key}
            onChange={(e) => setDraft({ ...draft, key: e.target.value })}
          />
        ) : (
          <>
            <p className="text-sm font-medium text-white/85">{humanizeKey(memory.key)}</p>
            <p className="text-[11px] text-white/35">
              {memory.category} · from {memory.source}
              {memory.sensitive ? " · sensitive" : ""}
            </p>
          </>
        )}
      </div>

      <div className="min-w-0 flex-1">
        {editing ? (
          <textarea
            className="input min-h-[60px] text-sm"
            value={draft.value}
            onChange={(e) => setDraft({ ...draft, value: e.target.value })}
          />
        ) : (
          <p className="text-sm leading-relaxed text-white/70">{memory.value}</p>
        )}
      </div>

      <div className="flex shrink-0 gap-1.5">
        {editing ? (
          <>
            <button onClick={save} disabled={busy} className="btn-ghost !px-2.5 !py-1 text-xs">
              Save
            </button>
            <button
              onClick={() => {
                setDraft({ category: memory.category, key: memory.key, value: memory.value });
                setEditing(false);
              }}
              className="btn-ghost !px-2.5 !py-1 text-xs"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => setEditing(true)}
              className="btn-ghost !px-2.5 !py-1 text-xs"
            >
              Edit
            </button>
            <button
              onClick={onDelete}
              className="btn-ghost !px-2.5 !py-1 text-xs hover:!text-red-300"
            >
              Delete
            </button>
          </>
        )}
      </div>
    </div>
  );
}
