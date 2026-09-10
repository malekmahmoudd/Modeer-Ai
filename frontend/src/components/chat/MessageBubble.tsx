import Link from "next/link";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { ThinkingDots } from "@/components/ui/primitives";
import { renderMarkdown } from "@/lib/markdown";
import type { Agent, Message } from "@/types";

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
    return (
      <div className="user-message flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-lg border-2 border-ink bg-sun-pale px-4 py-2.5 text-[15px] leading-relaxed text-ink">
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

        {!streaming && contextUsed && (
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
