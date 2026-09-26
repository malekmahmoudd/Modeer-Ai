"use client";

import Link from "next/link";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { Icon } from "@/components/ui/Icon";
import { ErrorNote, PageHeader, SectionLabel, Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { useApi } from "@/lib/api";
import { calendarDay, countdown, formatNumber } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
import type { WeekReview as Week } from "@/types";

/**
 * The weekly review as a page: the same tracked data Leo is given, laid out
 * to scan. Plain counts and titles, added up on the server — no model call.
 */
export function WeekReview() {
  const { t, tn } = usePrefs();
  const { byId } = useAgents();
  const agentName = useAgentName();
  const { data: week, loading, error } = useApi<Week>("/briefings/week");

  const moved: { key: string; text: string; agent?: string }[] = week
    ? [
        ...(week.plan_steps_done ? [{ key: "steps", text: tn("week.steps", week.plan_steps_done) }] : []),
        ...Object.entries(week.checkins).map(([agent, n]) => ({
          key: `c-${agent}`,
          agent,
          text: tn("week.checkins", n, { name: agentName(byId(agent), agent) }),
        })),
        ...week.goals_done.map((title) => ({ key: `g-${title}`, text: t("week.goalDone", { title }) })),
        ...week.followups_passed.map((title) => ({ key: `f-${title}`, text: t("week.passed", { title }) })),
      ]
    : [];
  const spending = week ? Object.entries(week.spending) : [];

  return (
    <div className="anim-fade journal-page week-page">
      <PageHeader
        eyebrow={t("week.eyebrow")}
        title={t("week.title")}
        lede={t("week.lede")}
        action={
          <Link
            href={`/agents/modeer?q=${encodeURIComponent(t("week.askLeoPrompt"))}`}
            className="btn btn-pink shrink-0"
          >
            {t("week.askLeo")}
            <Icon name="arrow-right" size={16} />
          </Link>
        }
      />

      {loading && <Spinner />}
      {error && <ErrorNote message={t("week.error", { error })} />}

      {week && (
        <>
          <p className="eyebrow mb-6">
            {t("week.range", { from: calendarDay(week.from), to: calendarDay(week.to) })}
          </p>

          <div className="grid gap-8 md:grid-cols-2">
            <section>
              <SectionLabel>{t("week.moved")}</SectionLabel>
              {moved.length === 0 ? (
                <p className="border-2 border-dashed border-ink bg-paper-hi px-4 py-5 text-[14px] text-ink-soft">
                  {t("week.nothingMoved")}
                </p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {moved.map((item) => (
                    <li key={item.key} className="goal-card flex items-center gap-3 border-2 border-ink bg-paper-hi px-3 py-2.5">
                      {item.agent ? (
                        <AgentBadge slug={item.agent} size={30} />
                      ) : (
                        <Icon name="check" size={18} className="shrink-0 text-ink" />
                      )}
                      <span className="text-[14.5px] font-semibold text-ink" dir="auto">
                        {item.text}
                      </span>
                    </li>
                  ))}
                </ul>
              )}

              {spending.length > 0 && (
                <div className="mt-6">
                  <SectionLabel>{t("week.spending")}</SectionLabel>
                  <ul className="flex flex-wrap gap-2.5">
                    {spending.map(([currency, amount]) => (
                      <li key={currency} className="border-2 border-ink bg-sun px-3 py-2 text-[18px] font-black text-ink">
                        {t("week.spent", {
                          amount: formatNumber(amount, 2),
                          currency: currency.startsWith("no ") ? "" : currency,
                        })}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            <section>
              <SectionLabel>{t("week.next")}</SectionLabel>
              {week.coming_up.length === 0 && !week.plan_steps_due ? (
                <p className="border-2 border-dashed border-ink bg-paper-hi px-4 py-5 text-[14px] text-ink-soft">
                  {t("week.nothingNext")}
                </p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {week.coming_up.map((f) => (
                    <li key={`${f.title}-${f.due_on}`} className="goal-card flex items-center gap-3 border-2 border-ink bg-paper-hi px-3 py-2.5">
                      <AgentBadge slug={f.agent} size={30} />
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14.5px] font-semibold text-ink" dir="auto">
                          {f.title}
                        </span>
                        <span className="block text-[11.5px] font-bold uppercase tracking-wide text-ink-faint">
                          {calendarDay(f.due_on)} · {countdown(f.due_on)}
                        </span>
                      </span>
                    </li>
                  ))}
                  {week.plan_steps_due > 0 && (
                    <li className="goal-card flex items-center gap-3 border-2 border-ink bg-paper-hi px-3 py-2.5">
                      <Icon name="calendar" size={18} className="shrink-0" />
                      <Link href="/plans" className="text-[14.5px] font-semibold text-ink underline decoration-pink decoration-2 underline-offset-4">
                        {tn("week.stepsDue", week.plan_steps_due)}
                      </Link>
                    </li>
                  )}
                </ul>
              )}

              {week.quiet_goals.length > 0 && (
                <div className="mt-6">
                  <SectionLabel>{t("week.quiet")}</SectionLabel>
                  <ul className="flex flex-wrap gap-2">
                    {week.quiet_goals.map((title) => (
                      <li key={title}>
                        <Link href="/goals" className="chip" dir="auto">
                          {title}
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-[13px] text-ink-soft">{t("week.quietHelp")}</p>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
