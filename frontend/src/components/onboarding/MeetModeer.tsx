"use client";

import Link from "next/link";

import { AgentBadge, AgentPortrait } from "@/components/art/AgentPortrait";
import { HeroDiagonals, Scribble } from "@/components/art/Ink";
import { Icon } from "@/components/ui/Icon";
import { useAgents } from "@/features/agents/useAgents";

/** First run: meet Modeer, then a short conversation sets the team up. */
export function MeetModeer() {
  const { agents } = useAgents();
  const specialists = agents.filter((a) => !a.is_assistant);

  return (
    <div className="anim-fade">
      <section className="relative -mx-4 overflow-hidden border-b-2 border-ink sm:-mx-7">
        <HeroDiagonals />

        <div className="relative mx-auto grid w-full max-w-page grid-cols-1 items-end gap-x-6 px-4 pt-9 sm:px-7 md:grid-cols-[minmax(0,1fr)_minmax(0,0.95fr)]">
          <div className="pb-8 md:pb-12">
            <p className="eyebrow">First things first</p>
            <h1 className="display mt-2 text-[clamp(42px,9vw,78px)] text-ink">
              Meet
              <br />
              Modeer
            </h1>
            <p className="mt-4 max-w-[44ch] text-[clamp(16px,2vw,19px)] font-semibold leading-snug text-ink">
              Tell me a little about yourself — what you&apos;re studying or working on, what
              you&apos;re aiming for — and I&apos;ll get your whole team on the same page.
            </p>

            <Link href="/agents/modeer?onboarding=1" className="btn btn-pink mt-7 !text-[15px]">
              Start with Modeer
              <Icon name="arrow-right" size={17} />
            </Link>

            <p className="mt-3 text-[13px] font-semibold text-ink-soft">
              Takes about a minute. You can edit everything later in Memory.
            </p>

            <Scribble className="mt-6 block max-w-[210px]" underline>
              One conversation.
              <br />
              Nine specialists.
            </Scribble>
          </div>

          <div className="relative mx-auto h-[236px] w-full max-w-[300px] sm:h-[300px] sm:max-w-[370px] md:h-[420px] md:max-w-[440px]">
            <AgentPortrait
              slug="modeer"
              framing="hero"
              transparent
              fit="contain"
              className="absolute inset-x-0 bottom-0 h-full w-full"
            />
          </div>
        </div>
      </section>

      {specialists.length > 0 && (
        <section className="pt-8">
          <p className="eyebrow text-center">Then your team is ready</p>
          <ul className="mt-4 flex flex-wrap items-center justify-center gap-3">
            {specialists.map((a) => (
              <li key={a.id} className="flex items-center gap-2 border-2 border-ink bg-paper-hi px-2.5 py-1.5 shadow-pop-xs">
                <AgentBadge slug={a.id} size={30} />
                <span className="text-[13px] font-bold text-ink">
                  {a.name.replace(/ (Agent|Assistant)$/, "")}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
