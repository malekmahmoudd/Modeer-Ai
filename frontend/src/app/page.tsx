"use client";

import Link from "next/link";

import { AgentGrid } from "@/components/AgentGrid";
import { Scribble } from "@/components/art/Ink";
import { TodayBand } from "@/components/home/TodayBand";
import { ModeerHero } from "@/components/home/ModeerHero";
import { MeetModeer } from "@/components/onboarding/MeetModeer";
import { SectionHead } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import type { UserProfile } from "@/types";

export default function HomePage() {
  const { data: user, loading } = useApi<UserProfile>("/users/me");

  if (loading) {
    return (
      <div className="py-16" aria-busy>
        <div className="h-10 w-64 animate-pulse rounded bg-paper-lo" />
        <div className="mt-6 h-64 w-full animate-pulse rounded border-2 border-ink bg-paper-lo" />
      </div>
    );
  }

  if (user && !user.onboarded) return <MeetModeer />;

  return (
    <div className="anim-fade sunshine-home">
      <ModeerHero />

      <section className="sunshine-team-section">
        <SectionHead
          title="Your team"
          aside={
            <Scribble className="hidden max-w-[190px] text-right lg:block">
              Different minds.
              <br />
              A brighter you.
            </Scribble>
          }
        />
        <AgentGrid specialistsOnly featured />

        <div className="mt-5 flex justify-center md:justify-start">
          <Link href="/team" className="sunshine-all-team">
            Meet the whole team <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </section>

      <TodayBand />
    </div>
  );
}
