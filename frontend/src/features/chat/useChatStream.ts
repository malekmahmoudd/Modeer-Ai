"use client";

import { useCallback, useRef, useState } from "react";

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
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (message: string, conversationId: string | null) => {
      if (streaming) return;
      setText("");
      setStreaming(true);
      const controller = new AbortController();
      abortRef.current = controller;

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
        if (!res.ok || !res.body) throw new Error(`Stream failed (${res.status})`);

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
              opts.onError?.(evt.error);
            }
          }
        }
        void convId;
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          opts.onError?.(err instanceof Error ? err.message : "Stream error");
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [agentId, streaming, opts],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { send, stop, streaming, streamingText: text };
}
