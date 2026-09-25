import Link from "next/link";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { FileCard } from "@/components/chat/AttachFile";
import { ThinkingDots } from "@/components/ui/primitives";
import { renderMarkdown } from "@/lib/markdown";
import type { Agent, Completion, Message, RetrievedPassage } from "@/types";

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
const UNFINISHED: Record<Exclude<Completion, "completed">, string> = {
  truncated: "This reply reached its length limit and may be incomplete.",
  interrupted: "This reply stopped before it finished.",
  failed: "No reply arrived for this message.",
};

export function MessageBubble({
  message,
  agent,
  streaming = false,
}: {
  message: Message;
  agent: Agent;
  streaming?: boolean;
}) {
  if (message.role === "user") {
    const files = message.meta?.attachments ?? [];
    return (
      <div className="user-message flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-lg border-2 border-ink bg-sun-pale px-4 py-2.5 text-[15px] leading-relaxed text-ink">
          {files.length > 0 && (
            <span className="mb-2 flex flex-col gap-1.5">
              {files.map((f) => (
                <FileCard key={f.id} file={f} />
              ))}
            </span>
          )}
          {message.content}
        </div>
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
    <div className="assistant-message flex gap-3">
      <AgentBadge slug={agent.id} size={38} className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="message-author">{agent.name.replace(/ (Agent|Assistant)$/, "")}</p>
        <div className="prose-ink">
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
            {message.meta?.notice || UNFINISHED[ended]}
          </p>
        )}

        {!streaming && (ctx?.documents?.length ?? 0) > 0 && ended !== "failed" && (
          <p className="mt-2.5 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11.5px] font-bold uppercase tracking-wide text-ink-soft">
            <span className="h-2 w-2 rounded-full bg-sun" aria-hidden />
            From your files:
            {sourcesOf(ctx?.documents ?? []).map((s) => (
              <span key={s} className="normal-case tracking-normal text-ink">
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
            Personalised from your saved context
          </Link>
        )}
      </div>
    </div>
  );
}
