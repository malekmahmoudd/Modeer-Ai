"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { EmptyState, ErrorNote, SectionHead, Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { UPLOAD_TYPES, apiFetch, uploadDocument, useApi } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
import type { UserDocument } from "@/types";

const KB = 1024;

function size(bytes: number): string {
  return bytes >= KB * KB ? `${(bytes / KB / KB).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / KB))} KB`;
}

/** Files given to the team: upload, see whether each is ready, share or remove. */
export function DocumentsPanel() {
  const { agents } = useAgents();
  const { t, tn } = usePrefs();
  const agentName = useAgentName();
  const { data, loading, error, refetch } = useApi<UserDocument[]>("/documents");
  const [agentId, setAgentId] = useState("");
  const [shared, setShared] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  const docs = data ?? [];
  const processing = docs.some((d) => d.status === "processing");
  const name = (slug: string) => agentName(agents.find((a) => a.id === slug), slug);

  // A file is read in after it uploads; check back until it is ready or failed.
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(refetch, 2000);
    return () => clearInterval(timer);
  }, [processing, refetch]);

  useEffect(() => () => abortRef.current?.(), []);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !agentId) return;
    setErr(null);
    setProgress(0);
    setStatus(t("docs.uploading", { name: file.name }));
    const { promise, abort } = uploadDocument(file, agentId, {
      shared,
      onProgress: (f) => setProgress(f),
    });
    abortRef.current = abort;
    try {
      await promise;
      setStatus(t("docs.uploaded", { name: file.name }));
      if (fileRef.current) fileRef.current.value = "";
      refetch();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : t("upload.failed"));
      setStatus("");
    } finally {
      setProgress(null);
      abortRef.current = null;
    }
  }

  async function patch(doc: UserDocument, body: Partial<UserDocument>) {
    setErr(null);
    try {
      await apiFetch(`/documents/${doc.id}`, { method: "PATCH", body: JSON.stringify(body) });
      refetch();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : t("common.failed"));
    }
  }

  async function remove(doc: UserDocument) {
    setErr(null);
    try {
      await apiFetch(`/documents/${doc.id}`, { method: "DELETE" });
      setStatus(t("docs.deleted", { name: doc.filename }));
      refetch();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : t("docs.deleteError"));
    }
  }

  return (
    <section className="memory-files">
      <SectionHead title={t("docs.title")} />
      <p className="-mt-2 mb-5 text-[14px] font-semibold text-ink-soft">{t("docs.lede")}</p>

      <form onSubmit={upload} className="mb-6 border-2 border-ink bg-paper-hi p-3 shadow-pop-xs">
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1">
            <label htmlFor="doc-file" className="eyebrow mb-1 block">
              {t("docs.file")}
            </label>
            <input id="doc-file" ref={fileRef} type="file" accept={UPLOAD_TYPES} className="field" required />
          </div>
          <div>
            <label htmlFor="doc-agent" className="eyebrow mb-1 block">
              {t("docs.giveTo")}
            </label>
            <select
              id="doc-agent"
              className="field !w-auto"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              required
            >
              <option value="">{t("docs.choose")}</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {agentName(a)}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={progress !== null} className="btn btn-pink shrink-0">
            {progress !== null ? t("docs.uploadingPct", { n: Math.round(progress * 100) }) : t("docs.upload")}
          </button>
          {progress !== null && (
            <button type="button" onClick={() => abortRef.current?.()} className="btn shrink-0">
              {t("common.cancel")}
            </button>
          )}
        </div>
        <label className="mt-2.5 flex min-h-11 items-center gap-2.5 text-[14px] font-semibold text-ink">
          <input
            type="checkbox"
            className="h-5 w-5 accent-pink"
            checked={shared || agentId === "modeer"}
            disabled={agentId === "modeer"}
            onChange={(e) => setShared(e.target.checked)}
          />
          {t("docs.shareAll")}{agentId === "modeer" && t("docs.leoAlways")}
        </label>
      </form>

      <p className="sr-only" role="status" aria-live="polite">
        {status}
      </p>
      {err && (
        <div className="mb-4">
          <ErrorNote message={err} />
        </div>
      )}
      {loading && <Spinner />}
      {error && <ErrorNote message={t("docs.loadError", { error })} />}
      {!loading && !error && docs.length === 0 && (
        <EmptyState title={t("docs.none")}>{t("docs.noneHelp")}</EmptyState>
      )}

      <ul className="flex flex-col gap-2.5">
        {docs.map((d) => (
          <li key={d.id}>
            <div className="goal-card flex items-center gap-3 border-2 border-ink bg-paper-hi px-3 py-2.5 shadow-pop-xs">
              <Icon name="file" size={22} className="shrink-0 text-ink-soft" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] font-semibold leading-snug text-ink" dir="auto">{d.filename}</span>
                <span className="mt-0.5 block text-[11.5px] font-bold uppercase tracking-wide text-ink-faint">
                  {d.shared ? t("docs.wholeTeam") : t("docs.only", { name: name(d.agent_id) })} · {d.kind} · {size(d.size_bytes)}
                  {d.status === "ready" && d.pages > 1 && ` · ${tn("docs.pages", d.pages)}`}
                </span>
                {d.error && (
                  <span
                    role={d.status === "failed" ? "alert" : undefined}
                    className="mt-1 block text-[12.5px] font-bold text-pink-deep"
                  >
                    {d.error}
                  </span>
                )}
              </span>
              <span
                className={`shrink-0 border-2 border-ink px-2 py-0.5 text-[11.5px] font-black uppercase tracking-wide ${
                  d.status === "ready" ? "bg-sun text-ink" : d.status === "failed" ? "bg-pink text-ink" : "bg-paper-lo text-ink"
                }`}
              >
                {d.status === "processing" ? t("docs.reading") : d.status === "ready" ? t("docs.ready") : t("docs.failed")}
              </span>
              {d.status === "ready" && d.agent_id !== "modeer" && (
                <button
                  onClick={() => patch(d, { shared: !d.shared })}
                  className="btn !min-h-[40px] shrink-0 !text-[13px]"
                  aria-label={d.shared ? t("docs.makePrivateLabel", { file: d.filename, name: name(d.agent_id) }) : t("docs.shareLabel", { file: d.filename })}
                >
                  {d.shared ? t("docs.makePrivate") : t("docs.share")}
                </button>
              )}
              <button
                onClick={() => remove(d)}
                className="btn-icon !h-11 !w-11 shrink-0 hover:!bg-pink hover:!text-ink"
                aria-label={t("docs.deleteLabel", { file: d.filename })}
              >
                <Icon name="trash" size={17} />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
