"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";
import type { ChatStreamEvent, ContextDiagnostics, MemoryCandidate } from "@/types";

interface Options {
  onStart?: (conversationId: string, context: ContextDiagnostics) => void;
  onDelta?: (fullText: string) => void;
  onEnd?: (turn: {
    conversationId: string;
    context: ContextDiagnostics | null;
    contextUsed: boolean;
    content: string;
  }) => void;
  onMemory?: (info: {
    candidates: MemoryCandidate[];
    newlyOnboarded: boolean;
  }) => void;
  onError?: (message: string) => void;
}

/** Streams a chat turn from POST /agents/:id/chat/stream (SSE) into React state. */
export function useChatStream(agentId: string, opts: Options = {}) {
  const [streaming, setStreaming] = useState(false);
  const [text, setText] = useState("");
  const [replyComplete, setReplyComplete] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), [agentId]);

  const send = useCallback(
    async (message: string, conversationId: string | null) => {
      if (abortRef.current) return;
      setText("");
      setReplyComplete(false);
      setStreaming(true);
      const controller = new AbortController();
      abortRef.current = controller;

      const timeout = setTimeout(() => controller.abort("timeout"), 50000);
      let ended = false;
      let acc = "";
      let context: ContextDiagnostics | null = null;
      let convId = conversationId;

      try {
        const res = await fetch(`${API_BASE}/agents/${agentId}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, conversation_id: conversationId }),
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
              context = evt.context;
              opts.onStart?.(evt.conversation_id, evt.context);
            } else if (evt.type === "delta") {
              acc += evt.text;
              setText(acc);
              opts.onDelta?.(acc);
            } else if (evt.type === "end") {
              if (ended) continue;
              ended = true;
              setReplyComplete(true);
              convId = evt.conversation_id;
              opts.onEnd?.({
                conversationId: evt.conversation_id,
                context,
                contextUsed: evt.context_used,
                content: evt.content || acc,
              });
            } else if (evt.type === "memory") {
              opts.onMemory?.({
                candidates: evt.memory_candidates,
                newlyOnboarded: evt.newly_onboarded,
              });
            } else if (evt.type === "error") {
              throw new Error(evt.error);
            }
          }
        }
        if (!ended) throw new Error("The connection ended before the reply finished. Please try again.");
        void convId;
      } catch (err) {
        if (controller.signal.reason === "timeout") {
          opts.onError?.(ended ? "Your reply was saved, but memory processing timed out. Check Memory before relying on a new fact." : "The connection timed out. Please try again.");
        } else if ((err as Error).name !== "AbortError") {
          opts.onError?.(err instanceof Error ? err.message : "Stream error");
        }
      } finally {
        clearTimeout(timeout);
        setReplyComplete(true);
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [agentId, opts],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { send, stop, streaming, replyComplete, streamingText: text };
}
