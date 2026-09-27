"use client";

import Link from "next/link";
import { useState } from "react";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, ErrorNote, PageHeader, Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch, useApi } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
import type { Conversation } from "@/types";

interface Shelf {
  name: string;
  count: number;
}

type Filter = { kind: "all" } | { kind: "pinned" } | { kind: "folder"; name: string } | { kind: "loose" } | { kind: "tag"; name: string };

function query(filter: Filter): string {
  if (filter.kind === "folder") return `?folder=${encodeURIComponent(filter.name)}`;
  if (filter.kind === "loose") return "?folder=";
  if (filter.kind === "tag") return `?tag=${encodeURIComponent(filter.name)}`;
  return "";
}

/** Every chat with every teammate: pinned first, filed in folders, tagged. */
export function AllChats() {
  const { t } = usePrefs();
  const { byId } = useAgents();
  const agentName = useAgentName();
  const [filter, setFilter] = useState<Filter>({ kind: "all" });
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState("");
  const { data: shelves, refetch: refetchShelves } = useApi<{ folders: Shelf[]; tags: Shelf[] }>("/conversations/shelves");
  const { data, loading, setData } = useApi<Conversation[]>(`/conversations${query(filter)}`, [filter]);
  const chats = (data ?? []).filter((c) => filter.kind !== "pinned" || c.pinned_at);

  async function organise(id: string, changes: { pinned?: boolean; folder?: string; tags?: string[] }) {
    setError("");
    try {
      const updated = await apiFetch<Conversation>(`/conversations/${id}/organise`, {
        method: "PATCH",
        body: JSON.stringify(changes),
      });
      setData((data ?? []).map((c) => (c.id === id ? { ...c, ...updated } : c)));
      refetchShelves();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.failed"));
    }
  }

  const chip = (active: boolean) =>
    `inline-flex min-h-10 items-center gap-1.5 border-2 border-ink px-3 text-[13.5px] font-bold ${active ? "bg-sun" : "bg-paper-hi hover:bg-sun-pale"}`;
  const is = (f: Filter) => JSON.stringify(f) === JSON.stringify(filter);

  return (
    <div className="anim-fade">
      <PageHeader eyebrow={t("chats.eyebrow")} title={t("chats.title")} lede={t("chats.lede")} />
      <nav aria-label={t("chats.filters")} className="mb-5 flex flex-wrap gap-2">
        <button className={chip(is({ kind: "all" }))} aria-pressed={is({ kind: "all" })} onClick={() => setFilter({ kind: "all" })}>{t("chats.all")}</button>
        <button className={chip(is({ kind: "pinned" }))} aria-pressed={is({ kind: "pinned" })} onClick={() => setFilter({ kind: "pinned" })}>
          <Icon name="pin" size={15} /> {t("chats.pinned")}
        </button>
        {shelves?.folders.map((f) => (
          <button key={`f-${f.name}`} className={chip(is({ kind: "folder", name: f.name }))} aria-pressed={is({ kind: "folder", name: f.name })} onClick={() => setFilter({ kind: "folder", name: f.name })}>
            <Icon name="folder" size={15} /> <span dir="auto">{f.name}</span> <span className="text-ink-faint">{f.count}</span>
          </button>
        ))}
        {!!shelves?.folders.length && (
          <button className={chip(is({ kind: "loose" }))} aria-pressed={is({ kind: "loose" })} onClick={() => setFilter({ kind: "loose" })}>{t("chats.noFolder")}</button>
        )}
        {shelves?.tags.map((tag) => (
          <button key={`t-${tag.name}`} className={chip(is({ kind: "tag", name: tag.name }))} aria-pressed={is({ kind: "tag", name: tag.name })} onClick={() => setFilter({ kind: "tag", name: tag.name })}>
            <Icon name="tag" size={15} /> <span dir="auto">{tag.name}</span>
          </button>
        ))}
      </nav>
      {error && <div className="mb-4"><ErrorNote message={error} /></div>}
      {loading && !data ? (
        <Spinner />
      ) : !chats.length ? (
        <EmptyState title={t("chats.empty")}>{t("chats.emptyHelp")}</EmptyState>
      ) : (
        <ul className="space-y-2.5">
          {chats.map((c) => (
            <li key={c.id} className="border-2 border-ink bg-paper-hi">
              <div className="flex items-center gap-3 px-3 py-2.5">
                <AgentBadge slug={c.agent_id} size={36} />
                <Link href={`/agents/${c.agent_id}?c=${c.id}`} className="min-w-0 flex-1 hover:underline">
                  <span className="block truncate text-[15px] font-bold" dir="auto">{c.title}</span>
                  <span className="block text-[12px] font-semibold text-ink-faint">
                    {agentName(byId(c.agent_id), c.agent_id)}
                    {c.last_message_at ? ` · ${relativeTime(c.last_message_at)}` : ""}
                    {c.folder ? ` · ${c.folder}` : ""}
                  </span>
                  {!!c.tags?.length && (
                    <span className="mt-1 flex flex-wrap gap-1">
                      {c.tags.map((tag) => (
                        <span key={tag} className="border border-ink/40 bg-sun-pale px-1.5 text-[11.5px] font-bold" dir="auto">{tag}</span>
                      ))}
                    </span>
                  )}
                </Link>
                <button
                  className={`btn-icon shrink-0 ${c.pinned_at ? "!bg-sun" : ""}`}
                  aria-pressed={Boolean(c.pinned_at)}
                  aria-label={c.pinned_at ? t("chats.unpin", { title: c.title }) : t("chats.pin", { title: c.title })}
                  onClick={() => void organise(c.id, { pinned: !c.pinned_at })}
                >
                  <Icon name="pin" size={17} />
                </button>
                <button
                  className="btn-icon shrink-0"
                  aria-expanded={editing === c.id}
                  aria-label={t("chats.organise", { title: c.title })}
                  onClick={() => setEditing(editing === c.id ? null : c.id)}
                >
                  <Icon name="folder" size={17} />
                </button>
              </div>
              {editing === c.id && (
                <OrganiseForm
                  chat={c}
                  folders={shelves?.folders.map((f) => f.name) ?? []}
                  onSave={async (folder, tags) => {
                    await organise(c.id, { folder, tags });
                    setEditing(null);
                  }}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function OrganiseForm({
  chat,
  folders,
  onSave,
}: {
  chat: Conversation;
  folders: string[];
  onSave: (folder: string, tags: string[]) => Promise<void>;
}) {
  const { t } = usePrefs();
  const [folder, setFolder] = useState(chat.folder ?? "");
  const [tags, setTags] = useState((chat.tags ?? []).join(", "));
  const [busy, setBusy] = useState(false);
  const list = `folders-${chat.id}`;
  return (
    <form
      className="grid gap-3 border-t-2 border-ink/15 px-3 py-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        await onSave(folder.trim(), tags.split(/[,،]/).map((tag) => tag.trim()).filter(Boolean).slice(0, 8));
        setBusy(false);
      }}
    >
      <label className="block font-bold">
        {t("chats.folder")}
        <input className="field mt-1 w-full" dir="auto" list={list} maxLength={60} value={folder} onChange={(e) => setFolder(e.target.value)} placeholder={t("chats.folderHint")} />
        <datalist id={list}>{folders.map((name) => <option key={name} value={name} />)}</datalist>
      </label>
      <label className="block font-bold">
        {t("chats.tags")}
        <input className="field mt-1 w-full" dir="auto" value={tags} onChange={(e) => setTags(e.target.value)} placeholder={t("chats.tagsHint")} />
      </label>
      <button className="btn btn-pink" disabled={busy}>{busy ? t("common.saving") : t("common.save")}</button>
    </form>
  );
}
