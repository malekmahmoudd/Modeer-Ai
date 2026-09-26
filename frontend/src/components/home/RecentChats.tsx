"use client";

import Link from "next/link";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { useAgents } from "@/features/agents/useAgents";
import { useApi } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
import type { Conversation } from "@/types";

/** The latest conversations with anyone on the team, one tap to continue. */
export function RecentChats() {
  const { t } = usePrefs();
  const { byId } = useAgents();
  const agentName = useAgentName();
  const { data } = useApi<Conversation[]>("/conversations/recent");
  const recent = (data ?? []).filter((c) => c.last_message_at).slice(0, 4);
  if (!recent.length) return null;

  return (
    <section className="sunshine-team-section" aria-labelledby="recent-title">
      <h2 id="recent-title" className="eyebrow mb-3">
        {t("home.recent")}
      </h2>
      <ul className="grid gap-2.5 sm:grid-cols-2">
        {recent.map((c) => (
          <li key={c.id}>
            <Link
              href={`/agents/${c.agent_id}?c=${c.id}`}
              className="flex items-center gap-3 border border-ink bg-paper-hi px-3 py-2.5 transition hover:bg-sun-pale"
            >
              <AgentBadge slug={c.agent_id} size={36} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[14px] font-semibold text-ink" dir="auto">
                  {c.title}
                </span>
                <span className="block text-[11.5px] font-semibold text-ink-faint">
                  {t("home.recentWith", { name: agentName(byId(c.agent_id), c.agent_id) })} ·{" "}
                  {relativeTime(c.last_message_at)}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
