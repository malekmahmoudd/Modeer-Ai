"use client";

import Link from "next/link";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { FileCard } from "@/components/chat/AttachFile";
import { ReplyActions } from "@/components/chat/MessageActions";
import { Icon } from "@/components/ui/Icon";
import { ThinkingDots } from "@/components/ui/primitives";
import { usePrefs } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { renderMarkdown } from "@/lib/markdown";
import type { Completion, Message, RetrievedPassage } from "@/types";

/** "cv.pdf p.2, p.3" — one entry per file, its pages in order. */
function sourcesOf(passages: RetrievedPassage[]): string[] {
  const pages = new Map<string, Set<number>>();
  for (const p of passages) {
    if (!pages.has(p.filename)) pages.set(p.filename, new Set());
    if (p.page) pages.get(p.filename)!.add(p.page);
  }
  return [...pages].map(([file, set]) =>
    set.size ? `${file} ${[...set].sort((a, b) => a - b).map((n) => `p.${n}`).join(", ")}` : file,
  );
}

// Shown under a reply that did not finish, when the server gave no notice.
const UNFINISHED: Record<Exclude<Completion, "completed">, MessageKey> = {
  truncated: "msg.truncated",
  interrupted: "msg.interrupted",
  failed: "msg.failed",
};

export function MessageBubble({
  message,
  agentId,
  agentName,
  streaming = false,
  highlighted = false,
  onEdit,
  onToggleSave,
  onRegenerate,
  queued,
}: {
  message: Message;
  agentId: string;
  agentName: string;
  streaming?: boolean;
  /** Opened from search: drawn attention to once. */
  highlighted?: boolean;
  /** On the latest message the person sent: take it back to change it. */
  onEdit?: () => void;
  onToggleSave?: () => void;
  onRegenerate?: () => void;
  /** Waiting for the connection, with a way to take it back. */
  queued?: { onCancel: () => void };
}) {
  const { t } = usePrefs();
  const ring = highlighted ? " ring-4 ring-pink ring-offset-2 ring-offset-paper-hi" : "";

  if (message.role === "user") {
    const files = message.meta?.attachments ?? [];
    return (
      <div id={`m-${message.id}`} className="user-message flex flex-col items-end gap-1">
        <div
          dir="auto"
          className={`max-w-[85%] whitespace-pre-wrap rounded-lg border-2 border-ink bg-sun-pale px-4 py-2.5 text-[15px] leading-relaxed text-ink${ring}`}
        >
          {files.length > 0 && (
            <span className="mb-2 flex flex-col gap-1.5">
              {files.map((f) => (
                <FileCard key={f.id} file={f} />
              ))}
            </span>
          )}
          {message.content}
        </div>
        {queued && (
          <p className="flex items-center gap-2 text-[12px] font-semibold text-ink-soft" role="status">
            <Icon name="offline" size={14} /> {t("chat.queued")}
            <button onClick={queued.onCancel} className="underline decoration-2 underline-offset-2">
              {t("chat.cancelQueued")}
            </button>
          </p>
        )}
        {onEdit && !queued && (
          <button
            onClick={onEdit}
            aria-label={t("msg.editLabel")}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-bold text-ink-soft transition hover:bg-sun-pale"
          >
            <Icon name="pencil" size={14} /> {t("msg.edit")}
          </button>
        )}
      </div>
    );
  }

  const ctx = message.meta?.context;
  const contextUsed =
    Boolean(message.meta?.context_used) ||
    (ctx?.personal_context_count ?? 0) > 0 ||
    (ctx?.agent_memory_used?.length ?? 0) > 0;
  const empty = !message.content;
  const ended = message.completion ?? "completed";

  return (
    <div id={`m-${message.id}`} className="assistant-message flex gap-3">
      <AgentBadge slug={agentId} size={38} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="message-author">{agentName}</p>
        <div className={`prose-ink${ring}`}>
          {empty && streaming ? (
            <ThinkingDots />
          ) : (
            <>
              {renderMarkdown(message.content)}
              {streaming && <span className="caret" aria-hidden />}
            </>
          )}
        </div>

        {!streaming && ended !== "completed" && (
          <p className="mt-2.5 text-[12.5px] font-semibold text-ink-soft">
            {message.meta?.notice || t(UNFINISHED[ended])}
          </p>
        )}

        {!streaming && (ctx?.documents?.length ?? 0) > 0 && ended !== "failed" && (
          <p className="mt-2.5 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11.5px] font-bold uppercase tracking-wide text-ink-soft">
            <span className="h-2 w-2 rounded-full bg-sun" aria-hidden />
            {t("msg.fromFiles")}
            {sourcesOf(ctx?.documents ?? []).map((s) => (
              <span key={s} className="normal-case tracking-normal text-ink" dir="auto">
                {s}
              </span>
            ))}
          </p>
        )}

        {!streaming && contextUsed && ended !== "failed" && (
          <Link
            href="/memory"
            className="mt-2.5 inline-flex items-center gap-1.5 text-[11.5px] font-bold uppercase tracking-wide text-ink-soft transition hover:text-pink-deep"
          >
            <span className="h-2 w-2 rounded-full bg-pink" aria-hidden />
            {t("msg.personalised")}
          </Link>
        )}

        {!streaming && !empty && (
          <ReplyActions
            agentId={agentId}
            text={message.content}
            saved={Boolean(message.pinned_at)}
            onToggleSave={onToggleSave}
            onRegenerate={onRegenerate}
          />
        )}
      </div>
    </div>
  );
}
