"use client";

import Link from "next/link";

import { AgentGrid } from "@/components/AgentGrid";
import { Scribble } from "@/components/art/Ink";
import { ModeerHero } from "@/components/home/ModeerHero";
import { RecentChats } from "@/components/home/RecentChats";
import { TodayBand } from "@/components/home/TodayBand";
import { SectionHead } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";
import type { UserProfile } from "@/types";

export default function HomePage() {
  const { data: user, loading } = useApi<UserProfile>("/users/me");
  const { t } = usePrefs();

  if (loading) {
    return (
      <div className="py-16" aria-busy>
        <div className="h-10 w-64 animate-pulse rounded bg-paper-lo" />
        <div className="mt-6 h-64 w-full animate-pulse rounded border-2 border-ink bg-paper-lo" />
      </div>
    );
  }

  return (
    <div className="anim-fade sunshine-home">
      <ModeerHero onboarding={!!user && !user.onboarded} />

      <RecentChats />

      <section className="sunshine-team-section">
        <SectionHead
          title={t("home.yourTeam")}
          aside={
            <Scribble className="hidden max-w-[190px] text-end lg:block">
              {t("home.scribble1")}
              <br />
              {t("home.scribble2")}
            </Scribble>
          }
        />
        <AgentGrid specialistsOnly featured />

        <div className="mt-5 flex justify-center md:justify-start">
          <Link href="/team" className="sunshine-all-team">
            {t("home.meetAll")} <span aria-hidden="true" className="rtl-flip inline-block">↗</span>
          </Link>
        </div>
      </section>

      <TodayBand />
    </div>
  );
}
