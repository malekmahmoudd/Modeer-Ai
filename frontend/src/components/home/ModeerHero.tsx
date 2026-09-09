"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { ThinkingDots } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch, useApi } from "@/lib/api";
import { hexToRgba } from "@/lib/format";
import type { Briefing, Goal } from "@/types";

export function ModeerHero() {
  const router = useRouter();
  const { byId } = useAgents();
  const { data: briefing, loading, setData } = useApi<Briefing>("/briefings/today");
  const { data: goals } = useApi<Goal[]>("/goals?status=active");
  const [draft, setDraft] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const activeGoals = goals?.length ?? 0;

  function openModeer(seed?: string) {
    const q = (seed ?? draft).trim();
    router.push(q ? `/agents/modeer?q=${encodeURIComponent(q)}` : "/agents/modeer");
  }

  async function refresh() {
    setRefreshing(true);
    try {
      setData(await apiFetch<Briefing>("/briefings/today?refresh=true"));
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <section
      className="card relative overflow-hidden p-6 sm:p-7"
      style={{ boxShadow: "var(--shadow-2)" }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-28 h-72 w-72 rounded-full blur-3xl"
        style={{ background: hexToRgba("#8b7bff", 0.16) }}
      />

      {/* identity */}
      <div className="flex items-center gap-3">
        <span
          className="grid h-11 w-11 place-items-center rounded-[13px] text-white"
          style={{
            background: "linear-gradient(150deg, #8b7bff, #5b46d6)",
            boxShadow: "0 10px 28px -12px rgba(139,123,255,0.8)",
          }}
        >
          <Icon name="compass" size={22} />
        </span>
        <div className="min-w-0">
          <p className="text-[15px] font-semibold tracking-tight text-white">Modeer</p>
          <p className="text-[12.5px] text-content-dim">Your personal assistant</p>
        </div>
        {activeGoals > 0 && (
          <button
            onClick={() => router.push("/goals")}
            className="tag ml-auto hover:text-white"
          >
            {activeGoals} active goal{activeGoals === 1 ? "" : "s"}
          </button>
        )}
      </div>

      {/* today */}
      <div className="mt-6">
        <div className="flex items-center gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-content-faint">
            Today
          </p>
          <button
            onClick={refresh}
            className="text-[11px] text-content-faint transition hover:text-content-dim"
          >
            {refreshing ? "…" : "refresh"}
          </button>
        </div>

        {loading ? (
          <div className="mt-3 flex items-center gap-2 text-[13px] text-content-faint">
            <ThinkingDots /> preparing your briefing
          </div>
        ) : briefing ? (
          <>
            <p className="mt-2 text-[15px] leading-relaxed text-white/90">{briefing.summary}</p>
            <ul className="mt-4 flex flex-col gap-1.5">
              {briefing.items.map((item, i) => {
                const agent = item.agent ? byId(item.agent) : undefined;
                const accent = agent?.accent ?? "var(--text-faint)";
                return (
                  <li key={i}>
                    <button
                      onClick={() =>
                        agent ? router.push(`/agents/${agent.id}`) : openModeer()
                      }
                      className="row-hover group flex w-full items-center gap-3 rounded-[10px] px-2.5 py-2 text-left"
                    >
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: accent }}
                      />
                      <span className="text-[13px]">{item.icon}</span>
                      <span className="min-w-0 flex-1">
                        {agent && (
                          <span
                            className="mr-1.5 text-[12px] font-medium"
                            style={{ color: hexToRgba(agent.accent, 0.95) }}
                          >
                            {agent.name.replace(" Agent", "")}
                          </span>
                        )}
                        <span className="text-[13.5px] text-content-dim group-hover:text-white">
                          {item.text}
                        </span>
                      </span>
                      <Icon
                        name="arrow-right"
                        size={14}
                        className="shrink-0 text-content-faint opacity-0 transition group-hover:opacity-100"
                      />
                    </button>
                  </li>
                );
              })}
            </ul>
          </>
        ) : null}
      </div>

      {/* composer */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          openModeer();
        }}
        className="mt-6 flex items-center gap-2 rounded-[12px] border border-line bg-bg-elev p-1.5 pl-3.5 focus-within:border-line-strong"
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Message Modeer…"
          className="min-w-0 flex-1 bg-transparent text-[13.5px] text-white outline-none placeholder:text-content-faint"
        />
        <button
          type="submit"
          className="grid h-8 w-8 place-items-center rounded-[9px] bg-white text-bg transition hover:bg-white/90"
          aria-label="Open Modeer"
        >
          <Icon name="arrow-up" size={16} />
        </button>
      </form>
    </section>
  );
}
