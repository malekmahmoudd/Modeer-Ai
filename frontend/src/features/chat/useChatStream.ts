"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";
import type {
  Allowance,
  ChatStreamEvent,
  Completion,
  ContextDiagnostics,
  GoalChangeNote,
  HandoffNote,
  MemoryCandidate,
  TrackedNote,
} from "@/types";

/** The browser's IANA timezone, so agents know what day it is for this person. */
function browserTimeZone(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
}

interface Options {
  onStart?: (conversationId: string, context: ContextDiagnostics) => void;
  onDelta?: (fullText: string) => void;
  onEnd?: (turn: {
    conversationId: string;
    context: ContextDiagnostics | null;
    contextUsed: boolean;
    content: string;
    completion: Completion;
    notice: string;
  }) => void;
  onMemory?: (info: {
    conversationId: string;
    candidates: MemoryCandidate[];
    goalChanges: GoalChangeNote[];
    handoffs: HandoffNote[];
    followups: TrackedNote[];
    followupsClosed: { id: string; title: string; outcome: string | null }[];
    checkins: TrackedNote[];
    plans: TrackedNote[];
    planProgress: TrackedNote[];
    allowance: Allowance | null;
    newlyOnboarded: boolean;
    error?: string;
  }) => void;
  /** `unfinishedIn` names the conversation when the server had started the
   *  turn, so it holds a record of how the reply ended. */
  onError?: (message: string, unfinishedIn: string | null) => void;
}

/** Streams a chat turn from POST /agents/:id/chat/stream (SSE) into React state. */
export function useChatStream(agentId: string, opts: Options = {}) {
  const [streaming, setStreaming] = useState(false);
  const [text, setText] = useState("");
  const [replyComplete, setReplyComplete] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  // Streams whose reply has ended but whose memory results are still arriving.
  // The composer is free again; these finish (or time out) in the background.
  const trailingRef = useRef<Set<AbortController>>(new Set());

  useEffect(
    () => () => {
      abortRef.current?.abort();
      trailingRef.current.forEach((c) => c.abort());
    },
    [agentId],
  );

  /** Send a message, or with `retry` regenerate the latest unfinished reply. */
  const send = useCallback(
    async (message: string | null, conversationId: string | null, retry = false, attachments: string[] = []) => {
      if (abortRef.current) return;
      setText("");
      setReplyComplete(false);
      setStreaming(true);
      const controller = new AbortController();
      abortRef.current = controller;

      let timeout = setTimeout(() => controller.abort("timeout"), 50000);
      let ended = false;
      let acc = "";
      let context: ContextDiagnostics | null = null;
      let convId = conversationId;
      let started: string | null = null;

      try {
        const res = await fetch(`${API_BASE}/agents/${agentId}/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(browserTimeZone() ? { "X-Timezone": browserTimeZone() as string } : {}),
          },
          body: JSON.stringify(
            retry
              ? { conversation_id: conversationId, retry: true }
              : { message, conversation_id: conversationId, attachments },
          ),
          signal: controller.signal,
        });
        if (res.status === 401) { window.location.assign("/login"); return; }
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(typeof body?.detail === "string" ? body.detail : `Stream failed (${res.status})`);
        }
        if (!res.body) throw new Error("The connection could not be opened. Please try again.");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() || "";
          for (const frame of frames) {
            const line = frame.trim();
            if (!line.startsWith("data:")) continue;
            let evt: ChatStreamEvent;
            try {
              evt = JSON.parse(line.slice(5).trim());
            } catch {
              continue;
            }
            if (evt.type === "start") {
              convId = evt.conversation_id;
              started = evt.conversation_id;
              context = evt.context;
              opts.onStart?.(evt.conversation_id, evt.context);
            } else if (evt.type === "delta") {
              acc += evt.text;
              setText(acc);
              opts.onDelta?.(acc);
            } else if (evt.type === "end") {
              if (ended) continue;
              ended = true;
              // The reply is saved and shown: free the composer now. Memory work
              // (what to remember, follow-ups, plans) is reported on this same
              // stream a few seconds later, and gets its own, shorter clock.
              clearTimeout(timeout);
              timeout = setTimeout(() => controller.abort("timeout"), 30000);
              trailingRef.current.add(controller);
              abortRef.current = null;
              setStreaming(false);
              setReplyComplete(true);
              convId = evt.conversation_id;
              opts.onEnd?.({
                conversationId: evt.conversation_id,
                context,
                contextUsed: evt.context_used,
                content: evt.content || acc,
                completion: evt.completion ?? "completed",
                notice: evt.notice ?? "",
              });
            } else if (evt.type === "memory") {
              opts.onMemory?.({
                conversationId: evt.conversation_id,
                candidates: evt.memory_candidates,
                goalChanges: evt.goal_changes ?? [],
                handoffs: evt.handoffs ?? [],
                followups: evt.followups ?? [],
                followupsClosed: evt.followups_closed ?? [],
                checkins: evt.checkins ?? [],
                plans: evt.plans ?? [],
                planProgress: evt.plan_progress ?? [],
                allowance: evt.allowance ?? null,
                newlyOnboarded: evt.newly_onboarded,
                error: evt.error,
              });
            } else if (evt.type === "error") {
              if (evt.conversation_id) started = evt.conversation_id;
              throw new Error(evt.error);
            }
          }
        }
        if (!ended) throw new Error("The connection ended before the reply finished. Please try again.");
        void convId;
      } catch (err) {
        const unfinishedIn = ended ? null : started;
        if (controller.signal.reason === "timeout") {
          opts.onError?.(ended ? "Your reply was saved, but memory processing timed out. Check Memory before relying on a new fact." : "The connection timed out. Please try again.", unfinishedIn);
        } else if ((err as Error).name !== "AbortError") {
          opts.onError?.(err instanceof Error ? err.message : "Stream error", unfinishedIn);
        }
      } finally {
        clearTimeout(timeout);
        trailingRef.current.delete(controller);
        // A newer message may already be streaming; only reset what is ours.
        if (abortRef.current === controller) {
          abortRef.current = null;
          setReplyComplete(true);
          setStreaming(false);
        }
      }
    },
    [agentId, opts],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { send, stop, streaming, replyComplete, streamingText: text };
}
