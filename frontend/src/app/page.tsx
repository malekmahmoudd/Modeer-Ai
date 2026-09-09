"use client";

import Link from "next/link";

import { AgentGrid } from "@/components/AgentGrid";
import { BriefingCard } from "@/components/BriefingCard";
import { GoalsPanel } from "@/components/GoalsPanel";
import { SectionHeading } from "@/components/ui/primitives";
import { useApi } from "@/lib/api";
import { greeting } from "@/lib/format";
import type { UserProfile } from "@/types";

export default function HomePage() {
  const { data: user } = useApi<UserProfile>("/users/me");
  const name = user?.display_name && user.display_name !== "You" ? user.display_name : undefined;

  return (
    <div className="mx-auto max-w-5xl animate-fade-up">
      <div className="mb-8">
        <p className="text-sm text-white/40">Your personal AI command center</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">
          {greeting(name)}
        </h1>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <BriefingCard />
        <div className="flex flex-col gap-5">
          <div className="card relative overflow-hidden p-6">
            <div className="flex items-center gap-3">
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 text-xl">
                🧭
              </span>
              <div>
                <p className="text-sm font-semibold text-white">Modeer</p>
                <p className="text-xs text-white/45">Personal assistant & context keeper</p>
              </div>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-white/55">
              Tell Modeer about yourself once. Every specialist on your team draws on
              the same shared context.
            </p>
            <Link href="/agents/modeer" className="btn-primary mt-4 w-full">
              Talk to Modeer
            </Link>
          </div>
          <GoalsPanel />
        </div>
      </div>

      <div className="mt-12">
        <SectionHeading
          title="Your AI team"
          hint="Pick a specialist and talk to them directly — no need to go through Modeer."
          action={
            <Link href="/team" className="btn-ghost hidden sm:inline-flex">
              View all
            </Link>
          }
        />
        <AgentGrid specialistsOnly />
      </div>
    </div>
  );
}
