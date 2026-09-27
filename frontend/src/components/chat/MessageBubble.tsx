"use client";

import { ReplyDetails } from "@/components/design/ReplyDetails";
import { ExcerptActions } from "@/components/design/ExcerptActions";
import { TeamComparison } from "@/components/design/TeamComparison";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { FileCard } from "@/components/chat/AttachFile";
import { ReplyActions } from "@/components/chat/MessageActions";
import { Icon } from "@/components/ui/Icon";
import { ThinkingDots } from "@/components/ui/primitives";
import { usePrefs } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import { renderMarkdown } from "@/lib/markdown";
import type { Completion, Message } from "@/types";

// Shown under a reply that did not finish, when the server gave no notice.
const UNFINISHED: Record<Exclude<Completion, "completed">, MessageKey> = {
  truncated: "msg.truncated",
  interrupted: "msg.interrupted",
  failed: "msg.failed",
};

export function MessageBubble({
  message,
  conversationId,
  onDraft,
  allowSave = true,
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
  conversationId?: string | null;
  onDraft?: (text: string) => void;
  allowSave?: boolean;
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

        {!streaming && conversationId && !empty && <ReplyDetails message={message} conversationId={conversationId} />}
        {!streaming && conversationId && !empty && onDraft && <ExcerptActions message={message} conversationId={conversationId} agentId={agentId} agentName={agentName} onDraft={onDraft} allowSave={allowSave} />}
        {!streaming && conversationId && message.meta.team && <TeamComparison conversationId={conversationId} />}

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
