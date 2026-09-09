"use client";

import Link from "next/link";

import { AgentGrid } from "@/components/AgentGrid";
import { AgentPortrait } from "@/components/art/AgentPortrait";
import { Scribble } from "@/components/art/Ink";
import { Icon } from "@/components/ui/Icon";
import { PageHeader, SectionHead } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";

export default function TeamPage() {
  const { byId, loading } = useAgents();
  const modeer = byId("modeer");

  return (
    <div className="anim-fade">
      <PageHeader
        eyebrow="Your AI team"
        title="Choose who to talk to"
        lede="Modeer keeps everyone in sync with what your team knows about you. Each specialist keeps its own conversation and its own private notes — you pick who you need."
      />

      {/* ---------- Modeer, featured ---------- */}
      {loading && <div className="h-[190px] animate-pulse border-2 border-ink bg-paper-lo shadow-pop" />}

      {modeer && (
        <Link
          href="/agents/modeer"
          className="group relative mb-10 grid grid-cols-[minmax(0,1fr)_128px] items-stretch overflow-hidden border-2 border-ink bg-sun shadow-pop transition-transform duration-150 hover:-translate-y-[3px] sm:grid-cols-[minmax(0,1fr)_210px]"
        >
          <div className="p-5 sm:p-7">
            <span className="tab-label">Personal assistant</span>
            <h2 className="display mt-3 text-[clamp(26px,4vw,40px)] text-ink">Modeer</h2>
            <p className="mt-2 max-w-[46ch] text-[14.5px] font-semibold leading-snug text-ink">
              Learns you, keeps the shared context, plans your day, and points you to the right
              specialist.
            </p>
            <span className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-black text-pink-deep">
              Talk to Modeer
              <Icon name="arrow-right" size={16} className="transition group-hover:translate-x-1" />
            </span>
          </div>
          <div className="relative overflow-hidden border-l-2 border-ink">
            <AgentPortrait
              slug="modeer"
              framing="panel"
              decorative
              className="absolute inset-0 h-full w-full"
            />
          </div>
        </Link>
      )}

      {/* ---------- specialists ---------- */}
      <SectionHead
        title="Specialists"
        aside={
          <Scribble className="hidden max-w-[170px] text-right lg:block">
            Nine minds,
            <br />
            one memory.
          </Scribble>
        }
      />
      <AgentGrid specialistsOnly size="lg" />
    </div>
  );
}
