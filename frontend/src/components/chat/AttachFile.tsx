"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { UPLOAD_TYPES, apiFetch, uploadDocument } from "@/lib/api";
import { t as tr, usePrefs } from "@/lib/i18n";
import type { Attachment, UserDocument } from "@/types";

/** A file picked in the message box, before the message is sent. */
export interface PendingFile {
  key: string;
  filename: string;
  size: number;
  status: "uploading" | "reading" | "ready" | "failed";
  progress: number;
  error?: string;
  doc?: UserDocument;
}

function sizeLabel(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/**
 * Files attached to the message being written. Each uploads straight away and
 * is read in by the server; the message can be sent once they are ready, and
 * they travel with it into the conversation.
 */
export function useAttachments(agentId: string) {
  const [files, setFiles] = useState<PendingFile[]>([]);
  const alive = useRef(true);
  const aborts = useRef(new Map<string, () => void>());

  useEffect(() => {
    // Set on every mount: development mounts twice, and the first cleanup
    // would otherwise leave this false for good.
    alive.current = true;
    const pending = aborts.current;
    return () => {
      alive.current = false;
      pending.forEach((abort) => abort());
    };
  }, []);

  const update = (key: string, patch: Partial<PendingFile>) =>
    alive.current && setFiles((all) => all.map((f) => (f.key === key ? { ...f, ...patch } : f)));

  const add = useCallback(
    async (file: File) => {
      const key = `${Date.now()}-${file.name}`;
      setFiles((all) => [...all, { key, filename: file.name, size: file.size, status: "uploading", progress: 0 }]);
      const upload = uploadDocument(file, agentId, { onProgress: (p) => update(key, { progress: p }) });
      aborts.current.set(key, upload.abort);
      try {
        let doc = await upload.promise;
        update(key, { status: "reading", doc });
        // Read in after upload; a few seconds for most files.
        for (let i = 0; i < 60 && alive.current && doc.status === "processing"; i++) {
          await new Promise((r) => setTimeout(r, 1500));
          doc = await apiFetch<UserDocument>(`/documents/${doc.id}`);
        }
        if (doc.status === "ready") update(key, { status: "ready", doc, error: doc.error ?? undefined });
        else update(key, { status: "failed", doc, error: doc.error || tr("attach.readFailed") });
      } catch (e) {
        update(key, { status: "failed", error: e instanceof Error ? e.message : tr("upload.failed") });
      } finally {
        aborts.current.delete(key);
      }
    },
    [agentId],
  );

  /** Take a file back off the message. Nothing was sent, so nothing is kept. */
  const remove = useCallback((file: PendingFile) => {
    aborts.current.get(file.key)?.();
    if (file.doc) apiFetch(`/documents/${file.doc.id}`, { method: "DELETE" }).catch(() => undefined);
    setFiles((all) => all.filter((f) => f.key !== file.key));
  }, []);

  const ready: Attachment[] = files
    .filter((f) => f.status === "ready" && f.doc)
    .map((f) => ({ id: f.doc!.id, filename: f.doc!.filename, kind: f.doc!.kind, size_bytes: f.doc!.size_bytes }));

  return {
    files,
    ready,
    busy: files.some((f) => f.status === "uploading" || f.status === "reading"),
    add,
    remove,
    /** After sending: the files now belong to the message. */
    clear: () => setFiles([]),
  };
}

/** The paperclip button in the message box. */
export function AttachButton({
  agentName,
  disabled,
  onPick,
}: {
  agentName: string;
  disabled?: boolean;
  onPick: (file: File) => void;
}) {
  const { t } = usePrefs();
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={input}
        type="file"
        accept={UPLOAD_TYPES}
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onPick(file);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={disabled}
        aria-label={t("attach.label", { name: agentName })}
        title={t("attach.title")}
        className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-ink-soft transition hover:bg-sun-pale hover:text-ink disabled:opacity-40"
      >
        <Icon name="paperclip" size={20} />
      </button>
    </>
  );
}

/** Chips for the files on the message being written, with their progress. */
export function AttachmentChips({ files, onRemove }: { files: PendingFile[]; onRemove: (file: PendingFile) => void }) {
  const { t } = usePrefs();
  if (!files.length) return null;
  return (
    <ul className="flex flex-wrap gap-2 px-1 pb-1.5 pt-0.5" aria-label={t("attach.files")}>
      {files.map((f) => {
        const state =
          f.status === "uploading"
            ? t("attach.uploading", { n: Math.round(f.progress * 100) })
            : f.status === "reading"
              ? t("attach.reading")
              : f.status === "failed"
                ? f.error
                : sizeLabel(f.size);
        return (
          <li
            key={f.key}
            className={`flex max-w-full items-center gap-2 border-2 border-ink py-1 pe-1 ps-2 text-[13px] ${
              f.status === "failed" ? "bg-pink-pale" : "bg-sun-pale"
            }`}
          >
            <Icon name="file" size={16} className="shrink-0" />
            <span className="min-w-0">
              <span className="block truncate font-bold text-ink" dir="auto">{f.filename}</span>
              <span
                className={`block text-[11.5px] font-semibold ${f.status === "failed" ? "text-pink-deep" : "text-ink-soft"}`}
                role={f.status === "failed" ? "alert" : undefined}
              >
                {state}
              </span>
            </span>
            <button
              type="button"
              onClick={() => onRemove(f)}
              aria-label={t("attach.remove", { name: f.filename })}
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full hover:bg-paper-lo"
            >
              <Icon name="x" size={14} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** A file shown on a sent message in the conversation. */
export function FileCard({ file }: { file: Attachment }) {
  return (
    <span className="flex items-center gap-2.5 border-2 border-ink bg-paper-hi px-2.5 py-1.5 text-start">
      <Icon name="file" size={20} className="shrink-0 text-ink-soft" />
      <span className="min-w-0">
        <span className="block truncate text-[13.5px] font-bold text-ink" dir="auto">{file.filename}</span>
        <span className="block text-[11px] font-bold uppercase tracking-wide text-ink-faint">
          {file.kind} · {sizeLabel(file.size_bytes)}
        </span>
      </span>
    </span>
  );
}
