"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AgentBadge, AgentPortrait } from "@/components/art/AgentPortrait";
import { Composer } from "@/components/chat/Composer";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { Icon } from "@/components/ui/Icon";
import { ErrorNote, Spinner } from "@/components/ui/primitives";
import { useChatStream } from "@/features/chat/useChatStream";
import { apiFetch, useApi } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type {
  AgentDetail,
  Conversation,
  ConversationDetail,
  MemoryCandidate,
  Message,
} from "@/types";

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
  const shortName = agent?.name.replace(/ (Agent|Assistant)$/, "") ?? "";

  if (loading) {
    return (
      <div className="grid flex-1 place-items-center py-24">
        <Spinner />
      </div>
    );
  }
  if (error || !agent) {
    return (
      <div className="mx-auto w-full max-w-page p-6">
        <ErrorNote message={error || "Agent not found"} />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-var(--nav-h))] flex-col bg-paper-hi">
      {/* ---------- identity header ---------- */}
      <header className="shrink-0 border-b-2 border-ink bg-paper">
        <div className="mx-auto flex w-full max-w-page items-center gap-3 px-3 py-2.5 sm:px-7">
          <button
            onClick={() => router.push("/team")}
            className="btn-icon !h-11 !w-11 shrink-0"
            aria-label="Back to your team"
          >
            <Icon name="chevron-left" size={20} />
          </button>

          <span className="relative shrink-0">
            {/* small geometric detail behind the portrait */}
            <span
              aria-hidden
              className="absolute -left-1 -top-1 h-11 w-11 bg-sun"
              style={{ clipPath: "polygon(0 0, 100% 0, 100% 70%, 0 100%)" }}
            />
            <AgentBadge slug={agent.id} size={46} className="relative" />
          </span>

          <div className="min-w-0 flex-1">
            <h1 className="display truncate text-[19px] leading-tight text-ink sm:text-[22px]">
              {agent.name}
            </h1>
            <p className="truncate text-[12.5px] font-semibold text-ink-soft">{agent.role}</p>
          </div>

          {convos.length > 0 && (
            <button
              onClick={() => setHistoryOpen(true)}
              className="btn-icon shrink-0"
              aria-label={`Conversation history (${convos.length})`}
              title="Conversations"
            >
              <Icon name="history" size={19} />
            </button>
          )}
          <button
            onClick={newConversation}
            className="btn-icon shrink-0"
            aria-label="Start a new conversation"
            title="New conversation"
          >
            <Icon name="plus" size={19} />
          </button>
        </div>
      </header>

      {/* ---------- transcript ---------- */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-7">
        <div className="mx-auto flex min-h-full w-full max-w-read flex-col py-6">
          {justOnboarded && (
            <div className="anim-in mb-6 flex flex-wrap items-center gap-3 border-2 border-ink bg-sun px-4 py-3 shadow-pop-sm">
              <Icon name="check" size={18} className="shrink-0 text-ink" />
              <p className="flex-1 text-[14px] font-bold text-ink">
                Your team is set up — everyone shares what you told Modeer.
              </p>
              <Link href="/team" className="btn btn-pink !min-h-[38px] !px-4 !text-[13px]">
                Meet your team
              </Link>
            </div>
          )}

          {!hasMessages && !streaming ? (
            <div className="anim-fade flex flex-1 flex-col items-center justify-center px-2 py-6 text-center">
              <div className="relative h-[168px] w-[150px] overflow-hidden border-2 border-ink shadow-pop">
                <AgentPortrait
                  slug={agent.id}
                  decorative
                  className="absolute inset-0 h-full w-full"
                />
              </div>
              <h2 className="display mt-6 max-w-[22ch] text-[clamp(21px,3.4vw,29px)] leading-tight text-ink">
                {onboarding && agent.id === "modeer"
                  ? "Hi — I'm Modeer. What are you working on right now?"
                  : agent.empty_prompt}
              </h2>
              {onboarding && agent.id === "modeer" && (
                <p className="mt-3 max-w-[40ch] text-[14px] font-semibold text-ink-soft">
                  A sentence or two is enough. I&apos;ll remember what matters and skip the rest.
                </p>
              )}
              {starters.length > 0 && (
                <ul className="mt-7 flex max-w-[34rem] flex-wrap justify-center gap-2.5">
                  {starters.map((s) => (
                    <li key={s}>
                      <button onClick={() => submit(s)} className="chip shadow-pop-xs">
                        {s}
                      </button>
                    </li>
                  ))}
                </ul>
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

      {/* ---------- composer ---------- */}
      <div className="shrink-0 border-t-2 border-ink bg-paper px-4 pb-[calc(70px+env(safe-area-inset-bottom))] pt-3 sm:px-7 md:pb-4">
        <div className="mx-auto w-full max-w-read">
          {savedFacts.length > 0 && (
            <div className="anim-in mb-2.5 flex items-start gap-2 border-2 border-ink bg-sun px-3 py-2 text-[13px] font-semibold text-ink">
              <Icon name="check" size={16} className="mt-px shrink-0" />
              <span>
                Saved to your context:{" "}
                {savedFacts.map((f, i) => (
                  <span key={i}>
                    {i > 0 && "; "}
                    {f.value}
                    {f.scope === "agent" ? ` (${shortName} only)` : ""}
                  </span>
                ))}
                .{" "}
                <Link href="/memory" className="underline decoration-2 underline-offset-2">
                  Manage
                </Link>
              </span>
            </div>
          )}
          {err && (
            <div className="mb-2.5">
              <ErrorNote message={err} />
            </div>
          )}

          <Composer
            value={input}
            onChange={setInput}
            onSend={() => submit(input)}
            streaming={streaming}
            placeholder={agent.composer_placeholder}
            autoFocus
          />
          <p className="mt-2 text-center text-[11.5px] font-semibold text-ink-faint">
            Uses your saved context, not other chats.
          </p>
        </div>
      </div>

      {/* ---------- conversation history ---------- */}
      {historyOpen && (
        <div
          className="anim-fade fixed inset-0 z-50 bg-ink/45"
          onClick={() => setHistoryOpen(false)}
          role="presentation"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Conversations"
            className="anim-in absolute inset-x-0 bottom-0 max-h-[72vh] overflow-y-auto border-t-2 border-ink bg-paper-hi p-4 pb-8 sm:inset-y-0 sm:left-auto sm:right-0 sm:max-h-none sm:w-[340px] sm:border-l-2 sm:border-t-0 sm:pb-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between gap-2">
              <h2 className="display text-[19px] text-ink">Conversations</h2>
              <div className="flex items-center gap-2">
                <button onClick={newConversation} className="btn !min-h-[38px] !px-3 !text-[13px]">
                  <Icon name="plus" size={15} /> New
                </button>
                <button
                  onClick={() => setHistoryOpen(false)}
                  className="btn-icon !h-[38px] !w-[38px]"
                  aria-label="Close conversations"
                >
                  <Icon name="x" size={16} />
                </button>
              </div>
            </div>

            <ul className="space-y-2">
              {convos.map((c) => {
                const active = c.id === conversationId;
                return (
                  <li key={c.id}>
                    <button
                      onClick={() => {
                        setConversationId(c.id);
                        setHistoryOpen(false);
                      }}
                      aria-current={active ? "true" : undefined}
                      className={`flex w-full flex-col gap-0.5 border-2 border-ink px-3 py-2.5 text-left transition ${
                        active ? "bg-sun shadow-pop-xs" : "bg-paper-hi hover:bg-sun-pale"
                      }`}
                    >
                      <span className="truncate text-[13.5px] font-bold text-ink">{c.title}</span>
                      <span className="text-[11.5px] font-semibold text-ink-faint">
                        {relativeTime(c.last_message_at || c.created_at)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
