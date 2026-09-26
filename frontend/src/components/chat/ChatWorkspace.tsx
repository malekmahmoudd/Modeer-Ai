"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { AgentBadge, AgentPortrait } from "@/components/art/AgentPortrait";
import { AttachButton, AttachmentChips, useAttachments } from "@/components/chat/AttachFile";
import { Composer } from "@/components/chat/Composer";
import { HANDOFF_KEY } from "@/components/chat/MessageActions";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { VoiceButton } from "@/components/chat/VoiceButton";
import { Icon } from "@/components/ui/Icon";
import { ErrorNote, Spinner } from "@/components/ui/primitives";
import { useChatStream } from "@/features/chat/useChatStream";
import { API_BASE, apiFetch, useApi } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { agentText } from "@/lib/i18n/agents";
import { draftKey, readDraft, useOnline, writeDraft } from "@/lib/offline";
import type {
  AgentDetail,
  Allowance,
  Conversation,
  ConversationDetail,
  MemoryCandidate,
  Message,
} from "@/types";

let tmp = 0;
const tmpId = () => `t${Date.now()}_${tmp++}`;

/** Remove an incognito chat on the server; `keepalive` lets it finish as the page closes. */
function discardIncognito(conversationId: string) {
  fetch(`${API_BASE}/conversations/${conversationId}`, { method: "DELETE", keepalive: true }).catch(
    () => undefined,
  );
}

export function ChatWorkspace({ agentId }: { agentId: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const { t, tn, locale } = usePrefs();
  const online = useOnline();
  const onboarding = params.get("onboarding") === "1";
  const seed = params.get("q");
  const openConversation = params.get("c");
  const focusMessage = params.get("m");

  const { data: agent, loading, error } = useApi<AgentDetail>(`/agents/${agentId}`, [agentId]);
  const { data: conversations, refetch: refetchConvos } = useApi<Conversation[]>(
    `/conversations?agent_id=${agentId}`,
    [agentId],
  );

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [err, setErr] = useState<string | null>(null);
  // Spoken, not shown: a reply that failed or stopped short says so in the
  // transcript, which a screen reader has no reason to revisit.
  const [announcement, setAnnouncement] = useState("");
  const attachments = useAttachments(agentId);
  const [savedFacts, setSavedFacts] = useState<MemoryCandidate[]>([]);
  const [teamNotes, setTeamNotes] = useState<string[]>([]);
  const [justOnboarded, setJustOnboarded] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState("");
  const creatingConversation = useRef(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);
  const [allowance, setAllowance] = useState<Allowance | null>(null);
  const [focusSignal, setFocusSignal] = useState(0);
  const [highlight, setHighlight] = useState<string | null>(null);
  // Incognito: `pending` is chosen but not yet sent; `active` has a conversation.
  const [incognito, setIncognito] = useState<{ context: boolean } | null>(null);
  const [incognitoAsk, setIncognitoAsk] = useState(false);
  const [incognitoContext, setIncognitoContext] = useState(false);
  // A message written while offline, sent when the connection returns.
  const [queued, setQueued] = useState<{ id: string; text: string } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const seededRef = useRef(false);
  const followReply = useRef(true);
  const historyRef = useRef<HTMLDivElement>(null);
  const liveConversation = useRef<string | null>(null);
  // The conversation on screen right now, for results that arrive late.
  const shownConversation = useRef<string | null>(null);
  const incognitoConversation = useRef<string | null>(null);
  useEffect(() => {
    shownConversation.current = conversationId;
  }, [conversationId]);

  const text = agent ? agentText(agent, locale) : null;
  const shortName = text?.name ?? "";

  // --- incognito: discard on leaving the chat, the agent or the page -----------------
  useEffect(() => {
    const onHide = () => incognitoConversation.current && discardIncognito(incognitoConversation.current);
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      onHide();
      incognitoConversation.current = null;
    };
  }, [agentId]);

  useEffect(() => {
    if (!historyOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const panel = historyRef.current;
    panel?.querySelector<HTMLElement>("button")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setHistoryOpen(false);
      if (e.key !== "Tab" || !panel) return;
      const items = Array.from(panel.querySelectorAll<HTMLElement>("button:not(:disabled), a[href], input"));
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); previous?.focus(); };
  }, [historyOpen]);

  useEffect(() => {
    setConversationId(openConversation);
    setMessages([]);
    setSavedFacts([]);
    setTeamNotes([]);
    setErr(null);
    setIncognito(null);
    seededRef.current = false;
    liveConversation.current = null;
    // Only when the agent changes; a later ?c= is handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentId]);

  // Opened from search or the home page: that conversation, that message.
  useEffect(() => {
    if (!openConversation) return;
    liveConversation.current = null;
    setIncognito(null);
    setConversationId(openConversation);
    if (focusMessage) setHighlight(focusMessage);
  }, [openConversation, focusMessage]);

  useEffect(() => {
    if (incognito || openConversation) return;
    if (conversationId === null && conversations && conversations.length > 0 && !seed && !params.get("handoff") && !params.get("draft")) {
      setConversationId(conversations[0].id);
    }
  }, [conversations, conversationId, seed, incognito, openConversation, params]);

  // Today's allowance, shown quietly under the message box.
  useEffect(() => {
    apiFetch<Allowance>("/usage/me").then(setAllowance).catch(() => undefined);
  }, []);

  const scrollDown = useCallback((smooth = true) => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: smooth ? "smooth" : "auto",
      });
    });
  }, []);

  useEffect(() => {
    if (!conversationId || liveConversation.current === conversationId) return;
    let on = true;
    apiFetch<ConversationDetail>(`/conversations/${conversationId}`)
      .then((c) => {
        if (!on) return;
        setMessages(c.messages);
        if (highlight && c.messages.some((m) => m.id === highlight)) {
          requestAnimationFrame(() =>
            document.getElementById(`m-${highlight}`)?.scrollIntoView({ block: "center" }),
          );
          setTimeout(() => setHighlight(null), 2600);
        } else {
          scrollDown(false);
        }
      })
      .catch(() => on && setMessages([]));
    return () => {
      on = false;
    };
    // `highlight` is read once per load, not a reason to reload.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, scrollDown]);

  // --- drafts: what was being typed survives a reload or a lost connection ------------
  const currentDraft = incognito ? null : draftKey(agentId, conversationId);
  const draftFor = useRef<string | null>(null);
  useEffect(() => {
    if (!currentDraft || draftFor.current === currentDraft) return;
    draftFor.current = currentDraft;
    const saved = readDraft(currentDraft);
    if (saved) setInput(saved);
  }, [currentDraft]);
  useEffect(() => {
    if (currentDraft && draftFor.current === currentDraft) writeDraft(currentDraft, input);
  }, [input, currentDraft]);

  // Arrived from "Ask a teammate": the quoted reply, ready to add a question to.
  useEffect(() => {
    let draft = params.get("draft");
    if (params.get("handoff")) {
      try {
        draft = window.sessionStorage.getItem(HANDOFF_KEY);
        window.sessionStorage.removeItem(HANDOFF_KEY);
      } catch {
        draft = null;
      }
    }
    if (!draft) return;
    setConversationId(null);
    setMessages([]);
    setInput(draft);
    setFocusSignal((n) => n + 1);
    router.replace(`/agents/${agentId}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const { send, stop, streaming, replyComplete, streamingText } = useChatStream(agentId, {
    onStart: (cid) => {
      liveConversation.current = cid;
      if (incognito) incognitoConversation.current = cid;
      setConversationId(cid);
      // A retry replaces the unfinished reply after the latest message; the
      // server has just removed it, so drop it here too.
      setMessages((prev) => prev.slice(0, prev.map((m) => m.role).lastIndexOf("user") + 1));
      scrollDown();
    },
    onDelta: () => { if (followReply.current) scrollDown(false); },
    onEnd: ({ messageId, content, context, contextUsed, completion, notice }) => {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== "streaming"),
        {
          id: messageId || tmpId(),
          role: "assistant",
          content,
          completion,
          created_at: new Date().toISOString(),
          meta: { context: context ?? undefined, context_used: contextUsed, notice },
        },
      ]);
      if (completion !== "completed") {
        setAnnouncement(notice || t("chat.unfinished"));
      }
      if (!incognito) refetchConvos();
      if (followReply.current) scrollDown(false);
    },
    onMemory: ({
      conversationId: memoryFor,
      candidates,
      goalChanges,
      handoffs,
      followups,
      followupsClosed,
      checkins,
      plans,
      planProgress,
      allowance: left,
      newlyOnboarded,
      error,
    }) => {
      if (left) setAllowance(left);
      // Memory results arrive after the reply; by then the person may have moved
      // to another conversation. Those notes belong to the one they came from.
      if (memoryFor && memoryFor !== shownConversation.current) return;
      if (error) {
        setErr(error);
        setAnnouncement(error);
      }
      const stored = candidates.filter((c) => c.stored);
      if (stored.length) setSavedFacts(stored);
      const notes = [
        ...goalChanges.filter((g) => g.applied).map((g) => t("chat.goalChanged", { title: g.title, reason: g.reason })),
        ...handoffs.filter((h) => h.stored).map((h) => t("chat.noteLeft", { name: h.agent_name })),
        // Say so when something asked for did not happen, and why.
        ...goalChanges.filter((g) => !g.applied).map((g) => t("chat.goalNotChanged", { title: g.title, reason: g.reason })),
        ...handoffs.filter((h) => !h.stored).map((h) => t("chat.noNote", { name: h.agent_name, reason: h.reason })),
        ...followupsClosed.map((f) => t("chat.closedFollowup", { title: f.title })),
        ...plans.map((p) => tn("chat.planSaved", p.steps ?? 0, { title: p.title ?? "" })),
        ...planProgress.map((p) => t("chat.ticked", { text: p.text ?? "" })),
        ...followups.filter((f) => f.stored).map((f) => t("chat.followupAdded", { title: f.title ?? "", date: f.due_on ?? "" })),
        ...checkins.filter((c) => c.stored).map((c) => t("chat.logged", { text: c.text ?? "" })),
        // Say so before the day's allowance runs out, not after.
        ...(left && left.messages_left <= 3
          ? [left.messages_left === 0 ? t("chat.allowanceUsed") : tn("chat.allowanceLeft", left.messages_left)]
          : []),
      ];
      if (notes.length) setTeamNotes(notes);
      if (newlyOnboarded) setJustOnboarded(true);
    },
    onError: (m, unfinishedIn) => {
      setMessages((prev) => prev.filter((x) => x.id !== "streaming"));
      setAnnouncement(m);
      if (!unfinishedIn) {
        setErr(m);
        return;
      }
      // The server recorded how this turn ended; show its record rather than
      // guessing — the transcript then says what happened and offers a retry.
      apiFetch<ConversationDetail>(`/conversations/${unfinishedIn}`)
        .then((c) => setMessages(c.messages))
        .catch(() => setErr(m));
    },
  });

  const submit = useCallback(
    async (typed: string) => {
      const files = attachments.ready;
      // A file on its own is a message too: "Here's cv.md."
      const message = typed.trim() || (files.length ? t("chat.hereIs", { files: files.map((f) => f.filename).join(", ") }) : "");
      if (!message || streaming || attachments.busy) return;
      followReply.current = true;
      setErr(null);
      setAnnouncement("");
      setSavedFacts([]);
      setTeamNotes([]);
      const id = tmpId();
      setMessages((prev) => [
        ...prev,
        // local: shown before the server has it, so it is nothing to retry yet.
        { id, role: "user", content: message, created_at: new Date().toISOString(), meta: { local: true, attachments: files } },
      ]);
      scrollDown();
      if (!navigator.onLine) {
        // Kept as the draft too, so a reload before the connection returns
        // loses nothing.
        setQueued({ id, text: message });
        setInput("");
        if (currentDraft) writeDraft(currentDraft, message);
        setAnnouncement(t("chat.offlineQueued"));
        return;
      }
      setInput("");
      if (currentDraft) writeDraft(currentDraft, "");
      attachments.clear();
      await send(message, conversationId, false, files.map((f) => f.id), incognito);
    },
    [streaming, send, conversationId, scrollDown, attachments, incognito, currentDraft, t],
  );

  // Back online: send what was written while away, once.
  useEffect(() => {
    if (!online || !queued || streaming) return;
    const waiting = queued;
    setQueued(null);
    setMessages((prev) => prev.filter((m) => m.id !== waiting.id));
    void submit(waiting.text);
  }, [online, queued, streaming, submit]);

  const retry = useCallback(async () => {
    if (streaming || !conversationId) return;
    followReply.current = true;
    setErr(null);
    setAnnouncement("");
    setSavedFacts([]);
    setTeamNotes([]);
    await send(null, conversationId, true);
  }, [streaming, send, conversationId]);

  /** Take back the latest turn: its reply (regenerate) or all of it (edit). */
  const rewind = useCallback(
    async (mode: "regenerate" | "edit") => {
      if (streaming || !conversationId) return;
      setErr(null);
      try {
        const back = await apiFetch<{ text: string }>(`/conversations/${conversationId}/rewind`, {
          method: "POST",
          body: JSON.stringify({ mode }),
        });
        const lastUser = messages.map((m) => m.role).lastIndexOf("user");
        if (mode === "regenerate") {
          setMessages((prev) => prev.slice(0, lastUser + 1));
          await retry();
        } else {
          setMessages((prev) => prev.slice(0, lastUser));
          setInput(back.text);
          setAnnouncement(t("chat.editing"));
          setFocusSignal((n) => n + 1);
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : t("chat.rewindError"));
      }
    },
    [streaming, conversationId, messages, retry, t],
  );

  const toggleSave = useCallback(
    async (message: Message) => {
      if (!conversationId) return;
      const pinned = !message.pinned_at;
      const stamp = pinned ? new Date().toISOString() : null;
      setMessages((prev) => prev.map((m) => (m.id === message.id ? { ...m, pinned_at: stamp } : m)));
      try {
        await apiFetch(`/conversations/${conversationId}/messages/${message.id}`, {
          method: "PATCH",
          body: JSON.stringify({ pinned }),
        });
      } catch (e) {
        setMessages((prev) => prev.map((m) => (m.id === message.id ? { ...m, pinned_at: message.pinned_at } : m)));
        setErr(e instanceof Error ? e.message : t("common.failed"));
      }
    },
    [conversationId, t],
  );

  useEffect(() => {
    if (seed && agent && !seededRef.current) {
      seededRef.current = true;
      submit(seed);
      router.replace(`/agents/${agentId}`);
    }
  }, [seed, agent, submit, router, agentId]);

  function startIncognito() {
    if (streaming) return;
    if (incognitoConversation.current) discardIncognito(incognitoConversation.current);
    incognitoConversation.current = null;
    liveConversation.current = null;
    setIncognito({ context: incognitoContext });
    setIncognitoAsk(false);
    setConversationId(null);
    setMessages([]);
    setSavedFacts([]);
    setTeamNotes([]);
    setInput("");
  }

  function leaveIncognito() {
    if (streaming) stop();
    if (incognitoConversation.current) discardIncognito(incognitoConversation.current);
    incognitoConversation.current = null;
    liveConversation.current = null;
    setIncognito(null);
    setMessages([]);
    setConversationId(conversations?.[0]?.id ?? null);
  }

  async function newConversation() {
    if (!agent || streaming || creatingConversation.current) return;
    if (incognito) leaveIncognito();
    creatingConversation.current = true;
    setErr(null);
    setHistoryError("");
    setAnnouncement("");
    try {
      const c = await apiFetch<ConversationDetail>("/conversations", {
        method: "POST",
        body: JSON.stringify({ agent_id: agent.id }),
      });
      setConversationId(c.id);
      setMessages([]);
      setSavedFacts([]);
      setTeamNotes([]);
      setHistoryOpen(false);
      refetchConvos();
    } catch {
      const notice = t("chat.newError");
      setErr(notice);
      setHistoryError(notice);
      setAnnouncement(notice);
    } finally {
      creatingConversation.current = false;
    }
  }

  async function rename(id: string, title: string) {
    const clean = title.trim();
    setRenaming(null);
    if (!clean) return;
    try {
      await apiFetch(`/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ title: clean }) });
      refetchConvos();
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : t("chat.renameError"));
    }
  }

  const starters = text?.starters ?? [];
  const convos = conversations ?? [];
  const hasMessages = messages.length > 0;

  // One explicit action when the latest turn has no finished reply. Nothing
  // retries on its own: every provider call here starts with a click.
  const latest = messages[messages.length - 1];
  const latestEnded = latest?.role === "assistant" ? (latest.completion ?? "completed") : null;
  const recovery =
    streaming || !latest || !conversationId || queued
      ? null
      : latestEnded === "truncated"
        ? { label: t("common.continue"), run: () => submit(t("chat.continuePrompt")) }
        : latestEnded === "failed" || latestEnded === "interrupted" || (latest.role === "user" && !latest.meta.local)
          ? { label: t("common.tryAgain"), run: retry }
          : null;
  const lastUserId = [...messages].reverse().find((m) => m.role === "user")?.id;
  const canRewind = !streaming && !!conversationId && latestEnded === "completed" && !queued;

  if (loading) {
    return (
      <div className="grid flex-1 place-items-center py-24">
        <Spinner />
      </div>
    );
  }
  if (error || !agent || !text) {
    return (
      <div className="mx-auto w-full max-w-page p-6">
        <ErrorNote message={error || t("agent.notFound")} />
      </div>
    );
  }

  const usedPct = allowance ? Math.max(0, Math.min(100, Math.round((allowance.remaining / Math.max(1, allowance.limit)) * 100))) : null;

  return (
    <div className={`comic-workspace flex h-[calc(100dvh-var(--nav-h))] flex-col bg-paper-hi ${incognito ? "incognito-workspace" : ""}`}>
      {/* ---------- identity header ---------- */}
      <header className="workspace-identity shrink-0 border-b-2 border-ink bg-paper">
        <div className="mx-auto flex w-full max-w-page items-center gap-3 px-3 py-2.5 sm:px-7">
          <button
            onClick={() => router.push("/team")}
            className="btn-icon !h-11 !w-11 shrink-0"
            aria-label={t("chat.back")}
          >
            <Icon name="chevron-left" size={20} />
          </button>

          <span className="relative shrink-0">
            {/* small geometric detail behind the portrait */}
            <span
              aria-hidden
              className="absolute -start-1 -top-1 h-11 w-11 bg-sun"
              style={{ clipPath: "polygon(0 0, 100% 0, 100% 70%, 0 100%)" }}
            />
            <AgentBadge slug={agent.id} size={46} className="relative" />
          </span>

          <div className="min-w-0 flex-1">
            <h1 className="display truncate text-[19px] leading-tight text-ink sm:text-[22px]">
              {text.name}
            </h1>
            <p className="truncate text-[12.5px] font-semibold text-ink-soft">{text.role}</p>
          </div>

          <button
            disabled={streaming}
            onClick={() => (incognito ? leaveIncognito() : setIncognitoAsk(!incognitoAsk))}
            className={`btn-icon shrink-0 ${incognito ? "!bg-navy !text-paper-hi" : ""}`}
            aria-label={incognito ? t("chat.incognitoEnd") : t("chat.incognitoStart")}
            aria-pressed={Boolean(incognito)}
            aria-expanded={incognito ? undefined : incognitoAsk}
            title={incognito ? t("chat.incognitoEnd") : t("chat.incognitoStart")}
          >
            <Icon name="incognito" size={19} />
          </button>
          {convos.length > 0 && (
            <button
              disabled={streaming}
              onClick={() => setHistoryOpen(true)}
              className="btn-icon shrink-0"
              aria-label={t("chat.historyLabel", { n: convos.length })}
              title={t("chat.conversations")}
            >
              <Icon name="history" size={19} />
            </button>
          )}
          <button
            disabled={streaming}
            onClick={newConversation}
            className="btn-icon shrink-0"
            aria-label={t("chat.newLabel")}
            title={t("chat.newTitle")}
          >
            <Icon name="plus" size={19} />
          </button>
        </div>
        {incognitoAsk && !incognito && (
          <div className="anim-in mx-auto w-full max-w-page px-3 pb-3 sm:px-7">
            <div role="region" aria-label={t("chat.incognitoTitle")} className="border-2 border-ink bg-paper-hi p-3 shadow-pop-xs">
              <p className="flex items-center gap-2 font-bold text-ink">
                <Icon name="incognito" size={18} /> {t("chat.incognitoTitle")}
              </p>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-soft">{t("chat.incognitoHelp")}</p>
              <label className="mt-2.5 flex min-h-11 items-center gap-2.5 text-[13.5px] font-semibold text-ink">
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-pink"
                  checked={incognitoContext}
                  onChange={(e) => setIncognitoContext(e.target.checked)}
                />
                {t("chat.incognitoContext")}
              </label>
              <div className="mt-2 flex gap-2">
                <button onClick={startIncognito} className="btn btn-pink !min-h-[40px] !text-[13px]">
                  {t("chat.incognitoGo")}
                </button>
                <button onClick={() => setIncognitoAsk(false)} className="btn !min-h-[40px] !text-[13px]">
                  {t("common.cancel")}
                </button>
              </div>
            </div>
          </div>
        )}
        {incognito && (
          <p className="incognito-banner flex items-center justify-center gap-2 px-4 py-1.5 text-center text-[12.5px] font-semibold">
            <Icon name="incognito" size={15} /> {t("chat.incognitoBanner")}
          </p>
        )}
      </header>

      {/* ---------- transcript ---------- */}
      <div ref={scrollRef} onScroll={() => { const el = scrollRef.current; if (el) followReply.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100; }} className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-7">
        <div className="mx-auto flex min-h-full w-full max-w-read flex-col py-6">
          {justOnboarded && (
            <div className="anim-in mb-6 flex flex-wrap items-center gap-3 border-2 border-ink bg-sun px-4 py-3 shadow-pop-sm">
              <Icon name="check" size={18} className="shrink-0 text-ink" />
              <p className="flex-1 text-[14px] font-bold text-ink">{t("chat.onboarded")}</p>
              <Link href="/team" className="btn btn-pink !min-h-[38px] !px-4 !text-[13px]">
                {t("chat.meetTeam")}
              </Link>
            </div>
          )}

          {!hasMessages && !streaming ? (
            <div className="workspace-welcome anim-fade flex flex-1 flex-col items-center justify-center px-2 py-6 text-center">
              <div className="welcome-portrait relative h-[168px] w-[150px] overflow-hidden border-2 border-ink shadow-pop">
                <AgentPortrait slug={agent.id} decorative className="absolute inset-0 h-full w-full" />
              </div>
              <h2 className="display mt-6 max-w-[22ch] text-[clamp(21px,3.4vw,29px)] leading-tight text-ink">
                {onboarding && agent.id === "modeer" ? t("chat.leoHello") : text.empty}
              </h2>
              {onboarding && agent.id === "modeer" && (
                <p className="mt-3 max-w-[40ch] text-[14px] font-semibold text-ink-soft">{t("chat.leoHint")}</p>
              )}
              {starters.length > 0 && (
                <ul className="welcome-starters mt-7 flex max-w-[34rem] flex-wrap justify-center gap-2.5">
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
              {messages.map((m, i) => {
                const isLatest = i === messages.length - 1;
                return (
                  <MessageBubble
                    key={m.id}
                    message={m}
                    agentId={agent.id}
                    agentName={text.name}
                    streaming={m.id === "streaming" && streaming}
                    highlighted={m.id === highlight}
                    queued={queued?.id === m.id ? { onCancel: () => {
                      setQueued(null);
                      setMessages((prev) => prev.filter((x) => x.id !== m.id));
                      setInput(m.content);
                    } } : undefined}
                    onEdit={canRewind && m.id === lastUserId && !latest?.pinned_at ? () => rewind("edit") : undefined}
                    onRegenerate={canRewind && isLatest && m.role === "assistant" && !m.pinned_at ? () => rewind("regenerate") : undefined}
                    onToggleSave={
                      m.role === "assistant" && !incognito && !m.id.startsWith("t") ? () => toggleSave(m) : undefined
                    }
                  />
                );
              })}
              {streaming && !replyComplete && (
                <MessageBubble
                  message={{ id: "streaming", role: "assistant", content: streamingText, created_at: "", meta: {} }}
                  agentId={agent.id}
                  agentName={text.name}
                  streaming
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* ---------- composer ---------- */}
      <div className="workspace-composer shrink-0 border-t-2 border-ink bg-paper px-4 pb-[calc(70px+env(safe-area-inset-bottom))] pt-3 sm:px-7 md:pb-4">
        <div className="mx-auto w-full max-w-read">
          {(savedFacts.length > 0 || teamNotes.length > 0) && (
            <div className="anim-in mb-2.5 flex items-start gap-2 border-2 border-ink bg-sun px-3 py-2 text-[13px] font-semibold text-ink">
              <Icon name="check" size={16} className="mt-px shrink-0" />
              <span>
                {savedFacts.length > 0 && (
                  <>
                    {t("chat.savedTo")}{" "}
                    {savedFacts.map((f, i) => (
                      <span key={i} dir="auto">
                        {i > 0 && "; "}
                        {f.value}
                        {f.previous_value ? ` ${t("chat.was", { value: f.previous_value })}` : ""}
                        {f.scope === "agent" ? ` ${t("chat.onlyAgent", { name: shortName })}` : ""}
                      </span>
                    ))}
                    .{" "}
                  </>
                )}
                {teamNotes.length > 0 && `${teamNotes.join(" ")} `}
                <Link href="/memory" className="underline decoration-2 underline-offset-2">
                  {t("common.manage")}
                </Link>
              </span>
            </div>
          )}
          {err && (
            <div className="mb-2.5">
              <ErrorNote message={err} />
            </div>
          )}
          <p className="sr-only" role="status" aria-live="polite">
            {announcement}
          </p>
          {recovery && (
            <div className="mb-2.5 flex justify-end">
              <button onClick={recovery.run} className="btn !min-h-[38px] !px-4 !text-[13px]">
                {recovery.label}
              </button>
            </div>
          )}

          <Composer
            value={input}
            onChange={setInput}
            onSend={() => submit(input)}
            streaming={streaming}
            placeholder={text.placeholder}
            autoFocus
            focusSignal={focusSignal}
            attach={<AttachButton agentName={shortName} disabled={streaming} onPick={attachments.add} />}
            chips={<AttachmentChips files={attachments.files} onRemove={attachments.remove} />}
            hasAttachments={attachments.ready.length > 0}
            waiting={attachments.busy}
            voice={
              <VoiceButton
                disabled={streaming}
                onText={(heard) => {
                  setInput((current) => (current.trim() ? `${current.trimEnd()} ${heard}` : heard));
                  setFocusSignal((n) => n + 1);
                }}
                onError={(message) => {
                  setErr(message);
                  setAnnouncement(message);
                }}
              />
            }
          />
          <div className="mt-2 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-center text-[11.5px] font-semibold text-ink-faint">
            <span>{incognito ? t("chat.incognitoFooter") : t("chat.footer")}</span>
            {allowance && usedPct !== null && (
              <span className="inline-flex items-center gap-1.5" title={`${t("usage.title")}. ${t("usage.resets")}`}>
                <span
                  className="relative inline-block h-1.5 w-14 overflow-hidden rounded-full border border-ink/40 bg-paper-lo"
                  role="meter"
                  aria-label={t("usage.title")}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={usedPct}
                  aria-valuetext={t("usage.left", { pct: usedPct })}
                >
                  <span
                    className={`absolute inset-y-0 start-0 ${usedPct <= 15 ? "bg-pink" : "bg-sun-deep"}`}
                    style={{ width: `${usedPct}%` }}
                  />
                </span>
                {tn("usage.leftMessages", allowance.messages_left)}
              </span>
            )}
          </div>
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
            ref={historyRef}
            role="dialog"
            aria-modal="true"
            aria-label={t("chat.conversations")}
            className="anim-in absolute inset-x-0 bottom-0 max-h-[72vh] overflow-y-auto border-t-2 border-ink bg-paper-hi p-4 pb-8 sm:inset-y-0 sm:end-0 sm:start-auto sm:max-h-none sm:w-[340px] sm:border-s-2 sm:border-t-0 sm:pb-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between gap-2">
              <h2 className="display text-[19px] text-ink">{t("chat.conversations")}</h2>
              <div className="flex items-center gap-2">
                <button onClick={newConversation} className="btn !min-h-[38px] !px-3 !text-[13px]">
                  <Icon name="plus" size={15} /> {t("chat.newShort")}
                </button>
                <button
                  onClick={() => setHistoryOpen(false)}
                  className="btn-icon !h-[38px] !w-[38px]"
                  aria-label={t("chat.closeHistory")}
                >
                  <Icon name="x" size={16} />
                </button>
              </div>
            </div>

            {historyError && <p role="alert" className="mb-3 text-pink-deep">{historyError}</p>}
            <ul className="space-y-2">
              {convos.map((c) => {
                const active = c.id === conversationId;
                if (renaming?.id === c.id) {
                  return (
                    <li key={c.id}>
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          void rename(c.id, renaming.title);
                        }}
                        className="flex items-center gap-2"
                      >
                        <label htmlFor={`rename-${c.id}`} className="sr-only">
                          {t("chat.renameField")}
                        </label>
                        <input
                          id={`rename-${c.id}`}
                          autoFocus
                          dir="auto"
                          maxLength={200}
                          className="field flex-1"
                          value={renaming.title}
                          onChange={(e) => setRenaming({ id: c.id, title: e.target.value })}
                          onKeyDown={(e) => e.key === "Escape" && (e.stopPropagation(), setRenaming(null))}
                        />
                        <button type="submit" className="btn-icon shrink-0" aria-label={t("common.save")}>
                          <Icon name="check" size={17} />
                        </button>
                      </form>
                    </li>
                  );
                }
                return (
                  <li key={c.id} className="flex items-stretch gap-1.5">
                    <button
                      onClick={() => {
                        // A reply still streaming belongs to the conversation it
                        // started in; stop it rather than let it land in this one.
                        if (streaming) stop();
                        if (incognito) leaveIncognito();
                        liveConversation.current = null;
                        setSavedFacts([]);
                        setTeamNotes([]);
                        setConversationId(c.id);
                        setHistoryOpen(false);
                      }}
                      aria-current={active ? "true" : undefined}
                      className={`flex min-w-0 flex-1 flex-col gap-0.5 border-2 border-ink px-3 py-2.5 text-start transition ${
                        active ? "bg-sun shadow-pop-xs" : "bg-paper-hi hover:bg-sun-pale"
                      }`}
                    >
                      <span className="truncate text-[13.5px] font-bold text-ink" dir="auto">{c.title}</span>
                      <span className="text-[11.5px] font-semibold text-ink-faint">
                        {relativeTime(c.last_message_at || c.created_at)}
                      </span>
                    </button>
                    <button
                      className="btn-icon shrink-0 self-center"
                      aria-label={t("chat.renameLabel", { title: c.title })}
                      disabled={streaming}
                      onClick={() => setRenaming({ id: c.id, title: c.title })}
                    >
                      <Icon name="pencil" size={16} />
                    </button>
                    <button className="btn-icon shrink-0 self-center" aria-label={t("chat.deleteLabel", { title: c.title })} disabled={!!deletingId || streaming} onClick={async () => {
                      if (!window.confirm(t("chat.deleteConfirm", { title: c.title }))) return;
                      setDeletingId(c.id); setHistoryError("");
                      try {
                        await apiFetch(`/conversations/${c.id}`, {method:"DELETE"});
                        await refetchConvos();
                        writeDraft(draftKey(agentId, c.id), "");
                        if (conversationId === c.id) { liveConversation.current = null; setConversationId(null); setMessages([]); setSavedFacts([]); setTeamNotes([]); }
                      } catch (e) { setHistoryError(e instanceof Error ? e.message : t("chat.deleteError")); }
                      finally { setDeletingId(null); }
                    }}><Icon name="trash" size={18}/></button>
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
