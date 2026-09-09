"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AgentAvatar } from "@/components/AgentAvatar";
import { Composer } from "@/components/chat/Composer";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { Icon } from "@/components/ui/Icon";
import { ErrorNote, Spinner } from "@/components/ui/primitives";
import { useChatStream } from "@/features/chat/useChatStream";
import { apiFetch, useApi } from "@/lib/api";
import { accentStyle, hexToRgba, relativeTime } from "@/lib/format";
import type { AgentDetail, Conversation, ConversationDetail, Message, MemoryCandidate } from "@/types";

let tmp = 0;
const tmpId = () => `t${Date.now()}_${tmp++}`;

export function ChatWorkspace({ agentId }: { agentId: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const onboarding = params.get("onboarding") === "1";
  const seed = params.get("q");

  const { data: agent, loading, error } = useApi<AgentDetail>(`/agents/${agentId}`, [agentId]);
  const { data: conversations, refetch: refetchConvos } = useApi<Conversation[]>(
    `/conversations?agent_id=${agentId}`,
    [agentId],
  );

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [savedFacts, setSavedFacts] = useState<MemoryCandidate[]>([]);
  const [justOnboarded, setJustOnboarded] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const seededRef = useRef(false);

  useEffect(() => {
    setConversationId(null);
    setMessages([]);
    setSavedFacts([]);
    setErr(null);
    seededRef.current = false;
  }, [agentId]);

  useEffect(() => {
    if (conversationId === null && conversations && conversations.length > 0 && !seed) {
      setConversationId(conversations[0].id);
    }
  }, [conversations, conversationId, seed]);

  const scrollDown = useCallback((smooth = true) => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: smooth ? "smooth" : "auto",
      });
    });
  }, []);

  useEffect(() => {
    if (!conversationId) return;
    let on = true;
    apiFetch<ConversationDetail>(`/conversations/${conversationId}`)
      .then((c) => {
        if (!on) return;
        setMessages(c.messages);
        scrollDown(false);
      })
      .catch(() => on && setMessages([]));
    return () => {
      on = false;
    };
  }, [conversationId, scrollDown]);

  const { send, streaming, streamingText } = useChatStream(agentId, {
    onStart: (cid) => {
      setConversationId(cid);
      scrollDown();
    },
    onDelta: () => scrollDown(),
    onEnd: ({ content, context, contextUsed }) => {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== "streaming"),
        {
          id: tmpId(),
          role: "assistant",
          content,
          created_at: new Date().toISOString(),
          meta: { context: context ?? undefined, context_used: contextUsed },
        },
      ]);
      refetchConvos();
      scrollDown();
    },
    onMemory: ({ candidates, newlyOnboarded }) => {
      const stored = candidates.filter((c) => c.stored);
      if (stored.length) setSavedFacts(stored);
      if (newlyOnboarded) setJustOnboarded(true);
    },
    onError: (m) => {
      setErr(m);
      setMessages((prev) => prev.filter((x) => x.id !== "streaming"));
    },
  });

  useEffect(() => {
    if (!streaming) return;
    setMessages((prev) => [
      ...prev.filter((m) => m.id !== "streaming"),
      {
        id: "streaming",
        role: "assistant",
        content: streamingText,
        created_at: new Date().toISOString(),
        meta: {},
      },
    ]);
  }, [streamingText, streaming]);

  const submit = useCallback(
    async (text: string) => {
      const t = text.trim();
      if (!t || streaming) return;
      setErr(null);
      setSavedFacts([]);
      setInput("");
      setMessages((prev) => [
        ...prev,
        { id: tmpId(), role: "user", content: t, created_at: new Date().toISOString(), meta: {} },
      ]);
      scrollDown();
      await send(t, conversationId);
    },
    [streaming, send, conversationId, scrollDown],
  );

  useEffect(() => {
    if (seed && agent && !seededRef.current) {
      seededRef.current = true;
      submit(seed);
      router.replace(`/agents/${agentId}`);
    }
  }, [seed, agent, submit, router, agentId]);

  async function newConversation() {
    if (!agent) return;
    const c = await apiFetch<ConversationDetail>("/conversations", {
      method: "POST",
      body: JSON.stringify({ agent_id: agent.id }),
    });
    setConversationId(c.id);
    setMessages([]);
    setSavedFacts([]);
    setHistoryOpen(false);
    refetchConvos();
  }

  const starters = useMemo(() => agent?.starters ?? [], [agent]);
  const convos = conversations ?? [];
  const hasMessages = messages.length > 0;

  if (loading) {
    return (
      <div className="grid h-dvh place-items-center text-content-faint">
        <Spinner />
      </div>
    );
  }
  if (error || !agent) {
    return <div className="p-6"><ErrorNote message={error || "Agent not found"} /></div>;
  }

  return (
    <div className="flex h-dvh flex-col" style={accentStyle(agent.accent)}>
      {/* Header */}
      <div className="shrink-0 px-4 pt-3.5 sm:px-6">
        <div className="mx-auto flex max-w-[46rem] items-center gap-3">
          <button
            onClick={() => router.push("/team")}
            className="btn-ghost -ml-2 h-9 w-9 !px-0"
            aria-label="Back to team"
          >
            <Icon name="chevron-left" size={18} />
          </button>
          <AgentAvatar icon={agent.icon} accent={agent.accent} size={34} />
          <div className="min-w-0 flex-1">
            <p className="text-[14.5px] font-semibold tracking-tight text-white">{agent.name}</p>
            <p className="truncate text-[12px] text-content-dim">{agent.tagline}</p>
          </div>
          {convos.length > 0 && (
            <button
              onClick={() => setHistoryOpen(true)}
              className="btn-ghost h-9 w-9 !px-0"
              aria-label="Conversation history"
              title="Conversations"
            >
              <Icon name="history" size={17} />
            </button>
          )}
          <button
            onClick={newConversation}
            className="btn-ghost h-9 w-9 !px-0"
            aria-label="New conversation"
            title="New conversation"
          >
            <Icon name="plus" size={17} />
          </button>
        </div>
        <div
          className="mx-auto mt-3.5 h-px max-w-[46rem]"
          style={{
            background: `linear-gradient(90deg, ${hexToRgba(agent.accent, 0.55)}, transparent 70%)`,
          }}
        />
      </div>

      <div className="flex min-h-0 flex-1 flex-col px-4 sm:px-6">
        {/* Chat column */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto flex min-h-full max-w-[46rem] flex-col py-6">
              {justOnboarded && (
                <div
                  className="anim-fade-up mb-6 flex items-center gap-3 rounded-[12px] border px-4 py-3"
                  style={{
                    borderColor: hexToRgba(agent.accent, 0.3),
                    background: hexToRgba(agent.accent, 0.08),
                  }}
                >
                  <Icon name="check" size={16} style={{ color: agent.accent }} />
                  <p className="flex-1 text-[13px] text-white/90">
                    Your team is set up — everyone now shares what you told Modeer.
                  </p>
                  <Link href="/team" className="text-[12.5px] font-medium text-white underline">
                    Meet your team
                  </Link>
                </div>
              )}

              {!hasMessages && !streaming ? (
                <div className="anim-fade-in flex flex-1 flex-col items-center justify-center px-4 text-center">
                  <AgentAvatar icon={agent.icon} accent={agent.accent} size={60} />
                  <h2 className="mt-5 max-w-md text-[19px] font-semibold leading-snug tracking-tight text-white">
                    {onboarding && agent.id === "modeer"
                      ? "Hi — I'm Modeer. What are you studying or working on right now?"
                      : agent.empty_prompt}
                  </h2>
                  {onboarding && agent.id === "modeer" && (
                    <p className="mt-2 max-w-sm text-[13px] text-content-dim">
                      A sentence or two is enough. I&apos;ll remember what matters and skip
                      the rest.
                    </p>
                  )}
                  {starters.length > 0 && (
                    <div className="mt-7 flex max-w-lg flex-wrap justify-center gap-2">
                      {starters.map((s) => (
                        <button
                          key={s}
                          onClick={() => submit(s)}
                          className="tag !px-3 !py-2 !text-[12px] transition hover:border-line-strong hover:text-white"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-6">
                  {messages.map((m) => (
                    <MessageBubble
                      key={m.id}
                      message={m}
                      agent={agent}
                      streaming={m.id === "streaming" && streaming}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="shrink-0 pb-[calc(56px+env(safe-area-inset-bottom))] pt-2 xl:pb-4">
            <div className="mx-auto w-full max-w-[46rem]">
              {savedFacts.length > 0 && (
                <div className="anim-fade-up mb-2 flex items-start gap-2 rounded-[10px] border border-emerald-500/20 bg-emerald-500/[0.07] px-3 py-2 text-[12px] text-emerald-200/90">
                  <Icon name="check" size={14} className="mt-0.5 shrink-0" />
                  <span>
                    Saved:{" "}
                    {savedFacts.map((f, i) => (
                      <span key={i}>
                        {i > 0 && "; "}
                        {f.value}
                        {f.scope === "agent" ? ` (${agent.name} only)` : ""}
                      </span>
                    ))}
                    .{" "}
                    <Link href="/memory" className="underline">
                      Manage
                    </Link>
                  </span>
                </div>
              )}
              {err && <div className="mb-2"><ErrorNote message={err} /></div>}
              <Composer
                value={input}
                onChange={setInput}
                onSend={() => submit(input)}
                streaming={streaming}
                placeholder={agent.composer_placeholder}
                autoFocus
              />
              <p className="mt-2 text-center text-[11px] text-content-faint">
                Uses your saved context, not other chats.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Conversation history — bottom sheet on mobile, right drawer on desktop */}
      {historyOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/50 anim-fade-in"
          onClick={() => setHistoryOpen(false)}
        >
          <div
            className="anim-fade-up absolute inset-x-0 bottom-0 max-h-[70vh] overflow-y-auto rounded-t-2xl border-t border-line bg-surface p-4 pb-8 sm:inset-y-0 sm:left-auto sm:right-0 sm:max-h-none sm:w-80 sm:rounded-none sm:border-l sm:border-t-0 sm:pb-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[13px] font-semibold text-white">Conversations</span>
              <div className="flex items-center gap-1">
                <button
                  onClick={newConversation}
                  className="btn-secondary h-8 text-[12px]"
                >
                  <Icon name="plus" size={14} /> New
                </button>
                <button
                  onClick={() => setHistoryOpen(false)}
                  className="btn-ghost h-8 w-8 !px-0"
                  aria-label="Close"
                >
                  <Icon name="x" size={15} />
                </button>
              </div>
            </div>
            {convos.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setConversationId(c.id);
                  setHistoryOpen(false);
                }}
                className={`flex w-full flex-col gap-0.5 rounded-[9px] px-3 py-2.5 text-left ${
                  c.id === conversationId ? "bg-surface-strong" : "hover:bg-surface-hover"
                }`}
              >
                <span className="truncate text-[13px] text-white/85">{c.title}</span>
                <span className="text-[11px] text-content-faint">
                  {relativeTime(c.last_message_at || c.created_at)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
