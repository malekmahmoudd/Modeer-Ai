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
      <header className="mb-6">
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-white">
          {greeting(name)}
        </h1>
      </header>

      <ModeerHero />

      <section className="mt-9">
        <div className="mb-4 flex items-end justify-between">
          <h2 className="text-[13px] font-semibold uppercase tracking-[0.12em] text-content-faint">
            Your team
          </h2>
          <Link
            href="/team"
            className="flex items-center gap-1 text-[12px] text-content-faint hover:text-content-dim"
          >
            All specialists <Icon name="arrow-right" size={12} />
          </Link>
        </div>
        <AgentGrid specialistsOnly />
      </section>
    </div>
  );
}
