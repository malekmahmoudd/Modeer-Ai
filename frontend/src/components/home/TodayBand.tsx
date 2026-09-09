"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { Icon } from "@/components/ui/Icon";
import { ThinkingDots } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch, useApi } from "@/lib/api";
import type { Briefing, Goal } from "@/types";

/**
 * Modeer's daily read — built only from goals and shared context already in
 * the product. Full-bleed yellow band under the team panels.
 */
export function TodayBand() {
  const router = useRouter();
  const { byId } = useAgents();
  const { data: briefing, loading, error, setData } = useApi<Briefing>("/briefings/today");
  const { data: goals } = useApi<Goal[]>("/goals?status=active");
  const [refreshing, setRefreshing] = useState(false);

  const focus = (briefing?.items ?? []).filter((i) => i.source !== "prompt").slice(0, 4);
  const activeGoals = goals?.length ?? 0;

  async function refresh() {
    setRefreshing(true);
    try {
      setData(await apiFetch<Briefing>("/briefings/today?refresh=true"));
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <section className="relative -mx-4 mt-12 border-y-2 border-ink bg-sun px-4 py-8 sm:-mx-7 sm:px-7">
      <div className="mx-auto w-full max-w-page">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 className="display text-[clamp(22px,3vw,30px)] text-ink">Today</h2>
          <span className="h-[2px] flex-1 bg-ink" aria-hidden />
          {activeGoals > 0 && (
            <Link href="/goals" className="chip">
              {activeGoals} active goal{activeGoals === 1 ? "" : "s"}
            </Link>
          )}
          <button
            onClick={refresh}
            disabled={refreshing}
            className="btn-icon !h-10 !w-10"
            aria-label="Refresh today's briefing"
            title="Refresh"
          >
            <Icon name="history" size={17} className={refreshing ? "animate-spin" : ""} />
          </button>
        </div>

        {loading && (
          <p className="mt-5 flex items-center gap-2 text-[14px] font-semibold text-ink-soft">
            <ThinkingDots /> Modeer is reading your priorities…
          </p>
        )}

        {error && (
          <p role="alert" className="mt-5 border-2 border-ink bg-paper-hi px-3 py-2 text-[14px] font-semibold">
            Couldn&apos;t load today&apos;s briefing: {error}
          </p>
        )}

        {briefing && !loading && (
          <>
            <p className="mt-4 max-w-[62ch] text-[clamp(16px,2vw,20px)] font-semibold leading-snug text-ink">
              {briefing.summary}
            </p>

            {focus.length > 0 && (
              <ul className="mt-5 grid gap-3 sm:grid-cols-2">
                {focus.map((item, i) => {
                  const agent = item.agent ? byId(item.agent) : undefined;
                  return (
                    <li key={i}>
                      <button
                        onClick={() =>
                          agent ? router.push(`/agents/${agent.id}`) : router.push("/agents/modeer")
                        }
                        className="group flex w-full items-center gap-3 border-2 border-ink bg-paper-hi px-3 py-2.5 text-left shadow-pop-xs transition hover:-translate-y-[2px] hover:shadow-pop-sm"
                      >
                        {agent ? (
                          <AgentBadge slug={agent.id} size={38} />
                        ) : (
                          <span className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-full border-2 border-ink bg-sun-pale">
                            <Icon name="goals" size={18} />
                          </span>
                        )}
                        <span className="min-w-0 flex-1">
                          {agent && (
                            <span className="block text-[11px] font-black uppercase tracking-wider text-pink-deep">
                              {agent.name.replace(/ (Agent|Assistant)$/, "")}
                            </span>
                          )}
                          <span className="block text-[14px] font-semibold leading-snug text-ink">
                            {item.text}
                          </span>
                        </span>
                        <Icon
                          name="arrow-right"
                          size={17}
                          className="shrink-0 text-ink-soft transition group-hover:translate-x-0.5"
                        />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
      </div>
    </section>
  );
}
