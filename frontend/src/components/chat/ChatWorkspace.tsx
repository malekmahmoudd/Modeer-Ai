"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AgentAvatar } from "@/components/AgentAvatar";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ErrorNote, Spinner } from "@/components/ui/primitives";
import { useChatStream } from "@/features/chat/useChatStream";
import { apiFetch, useApi } from "@/lib/api";
import { hexToRgba, relativeTime } from "@/lib/format";
import type {
  AgentDetail,
  Conversation,
  ConversationDetail,
  MemoryCandidate,
  Message,
} from "@/types";

let tmpId = 0;
const nextTmpId = () => `tmp-${Date.now()}-${tmpId++}`;

export function ChatWorkspace({ agentId }: { agentId: string }) {
  const { data: agent, loading: agentLoading, error: agentError } =
    useApi<AgentDetail>(`/agents/${agentId}`, [agentId]);
  const { data: conversations, refetch: refetchConversations } = useApi<Conversation[]>(
    `/conversations?agent_id=${agentId}`,
    [agentId],
  );

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [savedFacts, setSavedFacts] = useState<MemoryCandidate[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Pick the most recent conversation for this agent on load.
  useEffect(() => {
    setConversationId(null);
    setMessages([]);
    setSavedFacts([]);
  }, [agentId]);

  useEffect(() => {
    if (conversationId === null && conversations && conversations.length > 0) {
      setConversationId(conversations[0].id);
    }
  }, [conversations, conversationId]);

  useEffect(() => {
    if (!conversationId) return;
    let active = true;
    apiFetch<ConversationDetail>(`/conversations/${conversationId}`)
      .then((c) => active && setMessages(c.messages))
      .catch(() => active && setMessages([]));
    return () => {
      active = false;
    };
  }, [conversationId]);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }, []);

  const streamingRef = useRef<string>("");
  const { send, streaming, streamingText } = useChatStream(agentId, {
    onStart: (cid) => {
      setConversationId(cid);
      scrollToBottom();
    },
    onDelta: () => scrollToBottom(),
    onEnd: ({ content, contextUsed, context, memoryCandidates }) => {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== "streaming"),
        {
          id: nextTmpId(),
          role: "assistant",
          content,
          created_at: new Date().toISOString(),
          meta: { context: context ?? undefined, context_used: contextUsed },
        },
      ]);
      const stored = memoryCandidates.filter((c) => c.stored);
      if (stored.length) setSavedFacts(stored);
      refetchConversations();
      scrollToBottom();
    },
    onError: (msg) => {
      setError(msg);
      setMessages((prev) => prev.filter((m) => m.id !== "streaming"));
    },
  });

  useEffect(() => {
    streamingRef.current = streamingText;
    if (streaming) {
      setMessages((prev) => {
        const rest = prev.filter((m) => m.id !== "streaming");
        return [
          ...rest,
          {
            id: "streaming",
            role: "assistant",
            content: streamingText,
            created_at: new Date().toISOString(),
            meta: {},
          },
        ];
      });
    }
  }, [streamingText, streaming]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || streaming) return;
    setError(null);
    setSavedFacts([]);
    setInput("");
    setMessages((prev) => [
      ...prev,
      {
        id: nextTmpId(),
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
        meta: {},
      },
    ]);
    scrollToBottom();
    await send(text, conversationId);
  }

  async function newConversation() {
    if (!agent) return;
    const convo = await apiFetch<ConversationDetail>("/conversations", {
      method: "POST",
      body: JSON.stringify({ agent_id: agent.id }),
    });
    setConversationId(convo.id);
    setMessages([]);
    setSavedFacts([]);
    refetchConversations();
  }

  const suggestions = useMemo(() => SUGGESTIONS[agentId] ?? SUGGESTIONS._default, [agentId]);

  if (agentLoading) {
    return (
      <div className="flex h-[60vh] items-center justify-center text-white/40">
        <Spinner />
      </div>
    );
  }
  if (agentError || !agent) {
    return <ErrorNote message={agentError || "Agent not found"} />;
  }

  return (
    <div
      className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1fr_260px]"
      style={{ ["--accent" as string]: agent.accent }}
    >
      <div className="flex min-h-[70vh] flex-col">
        {/* Header */}
        <div
          className="card relative mb-4 overflow-hidden p-5"
          style={{
            background: `linear-gradient(120deg, ${hexToRgba(agent.accent, 0.12)}, rgba(255,255,255,0.02))`,
          }}
        >
          <div className="flex items-start gap-4">
            <AgentAvatar icon={agent.icon} accent={agent.accent} size={52} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-white">{agent.name}</h1>
                <span className="chip">{agent.role}</span>
              </div>
              <p className="mt-1 text-sm text-white/55">{agent.description}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {agent.expertise.slice(0, 4).map((e) => (
                  <span key={e} className="chip">
                    {e}
                  </span>
                ))}
              </div>
            </div>
            <Link href="/team" className="hidden text-white/30 hover:text-white/70 sm:block">
              ✕
            </Link>
          </div>
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="card flex-1 space-y-5 overflow-y-auto p-5"
        >
          {messages.length === 0 && !streaming && (
            <div className="flex h-full flex-col items-center justify-center gap-4 py-10 text-center">
              <AgentAvatar icon={agent.icon} accent={agent.accent} size={56} />
              <div>
                <p className="text-sm font-medium text-white/80">
                  Start a conversation with {agent.name}
                </p>
                <p className="mt-1 text-sm text-white/40">
                  {agent.name} already has access to what your team knows about you.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => setInput(s)}
                    className="chip hover:!text-white"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              agent={agent}
              streaming={m.id === "streaming" && streaming}
            />
          ))}
        </div>

        {savedFacts.length > 0 && (
          <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.07] px-3.5 py-2.5 text-xs text-emerald-200/90">
            <span className="font-medium">Saved to your context:</span>{" "}
            {savedFacts.map((f, i) => (
              <span key={i}>
                {i > 0 && ", "}
                {f.value}
                {f.scope === "agent" ? ` (${agent.name} only)` : ""}
              </span>
            ))}
            . Manage it in <Link href="/memory" className="underline">Memory</Link>.
          </div>
        )}
        {error && <div className="mt-3"><ErrorNote message={error} /></div>}

        {/* Composer */}
        <form onSubmit={handleSend} className="mt-3 flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend(e as unknown as React.FormEvent);
              }
            }}
            rows={1}
            placeholder={`Message ${agent.name}…`}
            className="input max-h-40 min-h-[46px] resize-none"
          />
          <button
            type="submit"
            disabled={streaming || !input.trim()}
            className="btn-primary h-[46px] px-5"
          >
            {streaming ? <Spinner className="border-ink-950/30 border-t-ink-950" /> : "Send"}
          </button>
        </form>
      </div>

      {/* Conversation rail */}
      <aside className="hidden flex-col gap-3 lg:flex">
        <button onClick={newConversation} className="btn-ghost w-full">
          + New conversation
        </button>
        <div className="card flex-1 overflow-y-auto p-2">
          {(conversations || []).length === 0 && (
            <p className="px-2 py-3 text-xs text-white/35">No conversations yet.</p>
          )}
          {(conversations || []).map((c) => (
            <button
              key={c.id}
              onClick={() => setConversationId(c.id)}
              className={`flex w-full flex-col gap-0.5 rounded-lg px-2.5 py-2 text-left transition ${
                c.id === conversationId
                  ? "bg-white/[0.08]"
                  : "hover:bg-white/[0.04]"
              }`}
            >
              <span className="truncate text-xs font-medium text-white/80">
                {c.title}
              </span>
              <span className="text-[10px] text-white/35">
                {relativeTime(c.last_message_at || c.created_at)}
              </span>
            </button>
          ))}
        </div>
        <div className="card p-3 text-[11px] leading-relaxed text-white/40">
          This conversation is private to {agent.name}. Other specialists can&apos;t
          see it — but they share your{" "}
          <Link href="/memory" className="text-white/60 underline">
            personal context
          </Link>
          .
        </div>
      </aside>
    </div>
  );
}

const SUGGESTIONS: Record<string, string[]> = {
  modeer: [
    "Help me set up my goals",
    "What should I focus on this week?",
    "Here's something about me you should know",
  ],
  study: ["Explain a concept I'm stuck on", "Build me a study plan", "Quiz me on a topic"],
  career: ["Review my next career move", "Help me prep for an interview", "Critique my CV summary"],
  research: ["Help me scope a research question", "Weigh the evidence on a topic"],
  writing: ["Edit a paragraph for me", "Help me outline a piece"],
  travel: ["Plan a trip", "Suggest a long weekend break"],
  shopping: ["Help me choose between two options", "Turn my need into buying criteria"],
  finance: ["Explain how to size an emergency fund", "Debt vs saving — how to think about it"],
  fitness: ["Build me a weekly training plan", "How do I keep a habit going?"],
  email: ["Draft a reply for me", "Make this message firmer but kind"],
  _default: ["What can you help me with?"],
};
