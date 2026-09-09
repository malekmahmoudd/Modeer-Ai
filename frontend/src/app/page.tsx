"use client";

import Link from "next/link";

import { AgentGrid } from "@/components/AgentGrid";
import { ModeerHero } from "@/components/home/ModeerHero";
import { MeetModeer } from "@/components/onboarding/MeetModeer";
import { Icon } from "@/components/ui/Icon";
import { useApi } from "@/lib/api";
import { firstName, greeting } from "@/lib/format";
import type { UserProfile } from "@/types";

export default function HomePage() {
  const { data: user, loading } = useApi<UserProfile>("/users/me");

  if (loading) {
    return <div className="h-40 animate-pulse rounded-lg bg-surface" />;
  }

  if (user && !user.onboarded) {
    return <MeetModeer />;
  }

  const name = firstName(user?.display_name);

  return (
    <div className="anim-fade-up">
      <header className="mb-8">
        <h1 className="text-[27px] font-semibold leading-tight tracking-[-0.02em] text-white">
          {greeting(name)}
        </h1>
      </header>

      <ModeerHero />

      <section className="mt-11">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="text-[15px] font-semibold tracking-tight text-white">Your team</h2>
            <p className="mt-0.5 text-[12.5px] text-content-dim">
              Nine specialists. Open any of them directly.
            </p>
          </div>
          <Link
            href="/team"
            className="hidden items-center gap-1 text-[12.5px] text-content-dim hover:text-white sm:flex"
          >
            All <Icon name="arrow-right" size={13} />
          </Link>
        </div>
        <AgentGrid specialistsOnly />
      </section>
    </div>
  );
}
