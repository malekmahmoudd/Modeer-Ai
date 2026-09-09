"use client";

import Link from "next/link";

import { AgentAvatar } from "@/components/AgentAvatar";
import { AgentGrid } from "@/components/AgentGrid";
import { Icon } from "@/components/ui/Icon";
import { PageHeader, SectionLabel } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";

export default function TeamPage() {
  const { byId } = useAgents();
  const modeer = byId("modeer");

  return (
    <div className="anim-fade-up">
      <PageHeader
        eyebrow="Your AI team"
        title="Choose who to talk to"
        lede="Modeer keeps everyone in sync with what your team knows about you. Each specialist keeps its own conversation and its own notes."
      />

      {modeer && (
        <Link
          href="/agents/modeer"
          className="lift card relative mb-8 flex items-center gap-3.5 overflow-hidden p-4"
        >
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 w-[3px]"
            style={{ background: modeer.accent }}
          />
          <AgentAvatar icon={modeer.icon} accent={modeer.accent} size={40} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="text-[14px] font-semibold tracking-tight text-white">Modeer</p>
              <span className="tag">Personal assistant</span>
            </div>
            <p className="mt-0.5 truncate text-[12.5px] text-content-dim">
              Learns you, keeps shared context, plans your day, points you to the right specialist.
            </p>
          </div>
          <Icon name="arrow-right" size={16} className="shrink-0 text-content-faint" />
        </Link>
      )}

      <SectionLabel>Specialists</SectionLabel>
      <AgentGrid specialistsOnly />
    </div>
  );
}
