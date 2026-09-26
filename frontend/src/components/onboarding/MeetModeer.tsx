"use client";

import Link from "next/link";

import { AgentBadge, AgentPortrait } from "@/components/art/AgentPortrait";
import { HeroDiagonals, Scribble } from "@/components/art/Ink";
import { Icon } from "@/components/ui/Icon";
import { useAgents } from "@/features/agents/useAgents";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";

/** First run: meet Modeer, then a short conversation sets the team up. */
export function MeetModeer() {
  const { agents } = useAgents();
  const { t } = usePrefs();
  const agentName = useAgentName();
  const specialists = agents.filter((a) => !a.is_assistant);

  return (
    <div className="anim-fade">
      <section className="relative -mx-4 overflow-hidden border-b-2 border-ink sm:-mx-7">
        <HeroDiagonals />

        <div className="relative mx-auto grid w-full max-w-page grid-cols-1 items-end gap-x-6 px-4 pt-9 sm:px-7 md:grid-cols-[minmax(0,1fr)_minmax(0,0.95fr)]">
          <div className="pb-8 md:pb-12">
            <p className="eyebrow">{t("meet.eyebrow")}</p>
            <h1 className="display mt-2 text-[clamp(42px,9vw,78px)] text-ink">
              {t("hero.meet")}
              <br />
              {t("common.leo")}
            </h1>
            <p className="mt-4 max-w-[44ch] text-[clamp(16px,2vw,19px)] font-semibold leading-snug text-ink">
              {t("meet.intro")}
            </p>

            <Link href="/agents/modeer?onboarding=1" className="btn btn-pink mt-7 !text-[15px]">
              {t("meet.start")}
              <Icon name="arrow-right" size={17} />
            </Link>

            <p className="mt-3 text-[13px] font-semibold text-ink-soft">
              {t("meet.time")}
            </p>

            <Scribble className="mt-6 block max-w-[210px]" underline>
              {t("meet.scribble1")}
              <br />
              {t("meet.scribble2")}
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
          <p className="eyebrow text-center">{t("meet.then")}</p>
          <ul className="mt-4 flex flex-wrap items-center justify-center gap-3">
            {specialists.map((a) => (
              <li key={a.id} className="flex items-center gap-2 border-2 border-ink bg-paper-hi px-2.5 py-1.5 shadow-pop-xs">
                <AgentBadge slug={a.id} size={30} />
                <span className="text-[13px] font-bold text-ink">
                  {agentName(a)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
