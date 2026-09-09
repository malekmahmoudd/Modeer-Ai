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
  const focusItems = (briefing?.items ?? [])
    .filter((it) => it.source !== "prompt")
    .slice(0, 4);

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
      className="card relative overflow-hidden"
      style={{ boxShadow: "var(--shadow-2)" }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-28 -top-28 h-64 w-64 rounded-full blur-3xl"
        style={{ background: hexToRgba("#8b7bff", 0.14) }}
      />

      <div className="grid gap-x-8 gap-y-5 p-5 lg:grid-cols-[1fr_300px]">
        {/* Left: identity + prompt */}
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <span
              className="grid h-10 w-10 place-items-center rounded-[12px] text-white"
              style={{
                background: "linear-gradient(150deg, #8b7bff, #5b46d6)",
                boxShadow: "0 10px 26px -12px rgba(139,123,255,0.8)",
              }}
            >
              <Icon name="compass" size={20} />
            </span>
            <div className="min-w-0">
              <p className="text-[14.5px] font-semibold tracking-tight text-white">Modeer</p>
              <p className="text-[12.5px] text-content-dim">Your personal assistant</p>
            </div>
          </div>

          {briefing && !loading && (
            <p className="mt-4 text-[15px] leading-relaxed text-white/90">
              {briefing.summary}
            </p>
          )}
          {loading && (
            <div className="mt-4 flex items-center gap-2 text-[13px] text-content-faint">
              <ThinkingDots /> preparing your briefing
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              openModeer();
            }}
            className="mt-4 flex items-center gap-2 rounded-[12px] border border-line bg-bg-elev p-1.5 pl-3.5 transition focus-within:border-line-strong"
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Message Modeer…"
              className="min-w-0 flex-1 bg-transparent text-[13.5px] text-white outline-none placeholder:text-content-faint"
            />
            <button
              type="submit"
              className="grid h-8 w-8 place-items-center rounded-[9px] text-white transition"
              style={{ background: "var(--accent)", color: "var(--accent-contrast)" }}
              aria-label="Open Modeer"
            >
              <Icon name="arrow-up" size={16} />
            </button>
          </form>
        </div>

        {/* Right: today's focus */}
        <div className="lg:border-l lg:border-line lg:pl-8">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-content-faint">
              Today&apos;s focus
            </p>
            <div className="flex items-center gap-2">
              {activeGoals > 0 && (
                <button
                  onClick={() => router.push("/goals")}
                  className="text-[11px] text-content-faint transition hover:text-content-dim"
                >
                  {activeGoals} goal{activeGoals === 1 ? "" : "s"}
                </button>
              )}
              <button
                onClick={refresh}
                className="grid h-6 w-6 place-items-center rounded-[7px] text-content-faint transition hover:bg-surface-strong hover:text-content-dim"
                aria-label="Refresh briefing"
              >
                <Icon name="history" size={13} className={refreshing ? "animate-spin" : ""} />
              </button>
            </div>
          </div>

          {focusItems.length > 0 ? (
            <ul className="-mx-2 flex flex-col">
              {focusItems.map((item, i) => {
                const agent = item.agent ? byId(item.agent) : undefined;
                const accent = agent?.accent ?? "var(--text-faint)";
                return (
                  <li key={i}>
                    <button
                      onClick={() =>
                        agent ? router.push(`/agents/${agent.id}`) : openModeer()
                      }
                      className="row-hover group flex w-full items-baseline gap-2.5 rounded-[9px] px-2 py-2 text-left"
                    >
                      <span
                        className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: accent }}
                      />
                      <span className="min-w-0 flex-1 text-[13px] leading-snug">
                        {agent && (
                          <span
                            className="font-medium"
                            style={{ color: hexToRgba(agent.accent, 0.95) }}
                          >
                            {agent.name.replace(" Agent", "").replace(" Assistant", "")}{" "}
                          </span>
                        )}
                        <span className="text-content-dim group-hover:text-white">
                          {item.text}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="px-2 text-[12.5px] leading-relaxed text-content-faint">
              Add a goal or two and this fills with what to focus on.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
