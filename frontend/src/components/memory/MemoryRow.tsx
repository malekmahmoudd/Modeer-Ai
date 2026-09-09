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
  const [draft, setDraft] = useState({ key: memory.key, value: memory.value });

  async function save() {
    setBusy(true);
    try {
      await onSave(draft);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <div className="rounded-[12px] border border-line-strong bg-bg-elev p-3">
        <input
          className="field mb-2 !py-2 text-[12.5px]"
          value={draft.key}
          onChange={(e) => setDraft({ ...draft, key: e.target.value })}
          placeholder="label"
        />
        <textarea
          className="field min-h-[64px]"
          value={draft.value}
          onChange={(e) => setDraft({ ...draft, value: e.target.value })}
        />
        <div className="mt-2 flex justify-end gap-2">
          <button
            onClick={() => {
              setDraft({ key: memory.key, value: memory.value });
              setEditing(false);
            }}
            className="btn-ghost h-8 text-[12px]"
          >
            Cancel
          </button>
          <button onClick={save} disabled={busy} className="btn-primary h-8 text-[12px]">
            Save
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="group row-hover flex items-center gap-3 rounded-[9px] px-2 py-2">
      <div className="min-w-0 flex-1">
        <span className="text-[13.5px] leading-snug text-content">{memory.value}</span>
        <span className="ml-2 text-[11px] text-content-faint">· {humanizeKey(memory.key)}</span>
        {memory.sensitive && (
          <span className="ml-2 rounded bg-amber-500/15 px-1 py-0.5 text-[9px] text-amber-300">
            sensitive
          </span>
        )}
      </div>
      <div className="flex shrink-0 gap-0.5 opacity-50 transition group-hover:opacity-100">
        <button
          onClick={() => setEditing(true)}
          className="grid h-7 w-7 place-items-center rounded-[8px] text-content-faint hover:bg-surface-strong hover:text-white"
          aria-label="Edit"
        >
          <Icon name="pencil" size={14} />
        </button>
        <button
          onClick={onDelete}
          className="grid h-7 w-7 place-items-center rounded-[8px] text-content-faint hover:bg-surface-strong hover:text-red-300"
          aria-label="Delete"
        >
          <Icon name="trash" size={14} />
        </button>
      </div>
    </div>
  );
}
