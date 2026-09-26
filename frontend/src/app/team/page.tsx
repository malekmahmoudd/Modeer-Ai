"use client";

import Link from "next/link";

import { AgentGrid } from "@/components/AgentGrid";
import { AgentPortrait } from "@/components/art/AgentPortrait";
import { Scribble } from "@/components/art/Ink";
import { Icon } from "@/components/ui/Icon";
import { PageHeader, SectionHead } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { usePrefs } from "@/lib/i18n";

export default function TeamPage() {
  const { byId, loading } = useAgents();
  const { t } = usePrefs();
  const modeer = byId("modeer");

  return (
    <div className="anim-fade team-page">
      <PageHeader
        eyebrow={t("team.eyebrow")}
        title={t("team.title")}
        lede={t("team.lede")}
      />

      {/* ---------- Modeer, featured ---------- */}
      {loading && <div className="h-[190px] animate-pulse border-2 border-ink bg-paper-lo shadow-pop" />}

      {modeer && (
        <Link
          href="/agents/modeer"
          className="team-feature group relative mb-10 grid grid-cols-[minmax(0,1fr)_128px] items-stretch overflow-hidden border-2 border-ink bg-sun shadow-pop transition-transform duration-150 hover:-translate-y-[3px] sm:grid-cols-[minmax(0,1fr)_210px]"
        >
          <div className="p-5 sm:p-7">
            <span className="tab-label">{t("team.assistant")}</span>
            <h2 className="display mt-3 text-[clamp(26px,4vw,40px)] text-ink">{t("common.leo")}</h2>
            <p className="mt-2 max-w-[46ch] text-[14.5px] font-semibold leading-snug text-ink">
              {t("team.leoBlurb")}
            </p>
            <span className="mt-4 inline-flex items-center gap-1.5 text-[14px] font-black text-pink-deep">
              {t("team.talkToLeo")}
              <Icon name="arrow-right" size={16} className="transition group-hover:translate-x-1" />
            </span>
          </div>
          <div className="relative overflow-hidden border-s-2 border-ink">
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
        title={t("team.specialists")}
        aside={
          <Scribble className="hidden max-w-[170px] text-end lg:block">
            {t("team.scribble1")}
            <br />
            {t("team.scribble2")}
          </Scribble>
        }
      />
      <AgentGrid specialistsOnly size="lg" />
    </div>
  );
}
