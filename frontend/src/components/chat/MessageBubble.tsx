import { AgentAvatar } from "@/components/AgentAvatar";
import type { Agent, Message } from "@/types";

function renderContent(text: string) {
  // Lightweight: paragraphs + bullet lines. No markdown dependency for the MVP.
  const blocks = text.split(/\n{2,}/);
  return blocks.map((block, i) => {
    const lines = block.split("\n");
    const isList = lines.every((l) => /^\s*([-*•]|\d+\.)\s+/.test(l));
    if (isList) {
      return (
        <ul key={i}>
          {lines.map((l, j) => (
            <li key={j}>{l.replace(/^\s*([-*•]|\d+\.)\s+/, "")}</li>
          ))}
        </ul>
      );
    }
    return <p key={i}>{block}</p>;
  });
}

export function MessageBubble({
  message,
  agent,
  streaming = false,
}: {
  message: Message;
  agent: Agent;
  streaming?: boolean;
}) {
  const isUser = message.role === "user";
  const contextCount =
    (message.meta?.context?.personal_context_count ?? 0) +
    (message.meta?.context?.agent_memory_used?.length ?? 0);

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-up">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-white px-4 py-2.5 text-sm leading-relaxed text-ink-950">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 animate-fade-up">
      <AgentAvatar icon={agent.icon} accent={agent.accent} size={32} />
      <div className="min-w-0 flex-1">
        <div className="prose-chat max-w-[85%] rounded-2xl rounded-tl-md border border-white/[0.06] bg-white/[0.03] px-4 py-3 text-sm leading-relaxed text-white/85">
          {message.content ? renderContent(message.content) : null}
          {streaming && (
            <span className="ml-0.5 inline-block h-3.5 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-white/60" />
          )}
        </div>
        {!streaming && contextCount > 0 && (
          <div className="mt-1.5 flex items-center gap-1.5 pl-1 text-[11px] text-white/35">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: agent.accent }}
            />
            {agent.name} used {contextCount} thing{contextCount === 1 ? "" : "s"} your
            team knows about you
          </div>
        )}
      </div>
    </div>
  );
}
