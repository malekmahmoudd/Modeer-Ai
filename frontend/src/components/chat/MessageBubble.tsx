import Link from "next/link";

import { AgentAvatar } from "@/components/AgentAvatar";
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
      <div className="flex justify-end">
        <div className="max-w-[82%] whitespace-pre-wrap rounded-[14px] rounded-br-[5px] bg-surface-strong px-3.5 py-2.5 text-[14px] leading-relaxed text-white">
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
    <div className="flex gap-3">
      <div className="pt-0.5">
        <AgentAvatar icon={agent.icon} accent={agent.accent} size={28} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="prose-chat max-w-[46rem]">
          {empty && streaming ? (
            <ThinkingDots />
          ) : (
            <>
              {renderMarkdown(message.content)}
              {streaming && <span className="caret" />}
            </>
          )}
        </div>
        {!streaming && contextUsed && (
          <Link
            href="/memory"
            className="mt-2 inline-flex items-center gap-1.5 text-[11.5px] text-content-faint transition hover:text-content-dim"
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: agent.accent }}
            />
            Personalized from your saved context
          </Link>
        )}
      </div>
    </div>
  );
}
