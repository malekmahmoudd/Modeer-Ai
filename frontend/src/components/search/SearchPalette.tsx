"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
import type { SearchHit } from "@/types";

/**
 * Find anything said in any conversation, with any teammate. Opens from the
 * search button or Ctrl/⌘-K; choosing a result opens that conversation.
 */
export function SearchPalette({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const { t } = usePrefs();
  const { byId } = useAgents();
  const agentName = useAgentName();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const panel = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    input.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key !== "Tab" || !panel.current) return;
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>("input, button"));
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [onClose]);

  // Search as they type, a moment after they pause.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setHits(null);
      setError("");
      return;
    }
    let live = true;
    const timer = setTimeout(async () => {
      setBusy(true);
      try {
        const found = await apiFetch<SearchHit[]>(`/conversations/search?q=${encodeURIComponent(q)}`);
        if (live) {
          setHits(found);
          setError("");
        }
      } catch {
        if (live) setError(t("search.error"));
      } finally {
        if (live) setBusy(false);
      }
    }, 250);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [query, t]);

  function open(hit: SearchHit) {
    onClose();
    router.push(`/agents/${hit.agent_id}?c=${hit.conversation_id}&m=${hit.message_id}`);
  }

  return (
    <div className="anim-fade fixed inset-0 z-[60] bg-ink/45" onClick={onClose} role="presentation">
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={t("search.title")}
        onClick={(e) => e.stopPropagation()}
        className="anim-in mx-auto mt-[8vh] flex max-h-[80vh] w-[min(640px,calc(100%-24px))] flex-col border-2 border-ink bg-paper-hi shadow-pop"
      >
        <div className="flex items-center gap-2 border-b-2 border-ink px-3 py-2">
          <Icon name="search" size={20} className="shrink-0 text-ink-soft" />
          <label htmlFor="search-input" className="sr-only">
            {t("search.title")}
          </label>
          <input
            id="search-input"
            ref={input}
            dir="auto"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("search.placeholder")}
            className="min-h-11 flex-1 bg-transparent text-[16px] text-ink outline-none placeholder:text-ink-faint"
            autoComplete="off"
          />
          {busy && <Spinner />}
          <button onClick={onClose} className="btn-icon !h-10 !w-10 shrink-0" aria-label={t("search.close")}>
            <Icon name="x" size={16} />
          </button>
        </div>

        <div className="overflow-y-auto p-2" aria-live="polite">
          {hits === null && !error && <p className="px-2 py-3 text-[13.5px] font-semibold text-ink-soft">{t("search.hint")}</p>}
          {error && <p role="alert" className="px-2 py-3 text-[13.5px] font-semibold text-pink-deep">{error}</p>}
          {hits?.length === 0 && (
            <p className="px-2 py-3 text-[13.5px] font-semibold text-ink-soft">{t("search.none", { q: query.trim() })}</p>
          )}
          <ul className="flex flex-col gap-1.5">
            {hits?.map((hit) => (
              <li key={hit.message_id}>
                <button
                  onClick={() => open(hit)}
                  className="flex w-full items-start gap-3 border-2 border-transparent px-2 py-2 text-start hover:border-ink hover:bg-sun-pale focus-visible:border-ink"
                >
                  <AgentBadge slug={hit.agent_id} size={34} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline gap-2 text-[12px] font-black uppercase tracking-wide text-pink-deep">
                      <span className="truncate">{agentName(byId(hit.agent_id), hit.agent_id)}</span>
                      <span className="truncate normal-case tracking-normal text-ink-faint" dir="auto">
                        {hit.title}
                      </span>
                    </span>
                    <span dir="auto" className="mt-0.5 block text-[14px] leading-snug text-ink">
                      {hit.role === "user" && <strong>{t("search.youSaid")}: </strong>}
                      {hit.snippet}
                    </span>
                    <span className="mt-0.5 block text-[11.5px] font-semibold text-ink-faint">
                      {relativeTime(hit.created_at)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
