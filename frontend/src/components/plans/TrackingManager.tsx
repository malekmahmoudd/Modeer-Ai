"use client";

import Link from "next/link";
import { useState } from "react";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, ErrorNote, PageHeader, SectionLabel, Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { API_BASE, apiFetch, useApi } from "@/lib/api";
import { calendarDay as day, countdown as when, daysFromToday, relativeTime } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
import { renderMarkdown } from "@/lib/markdown";
import type { CheckIn, FollowUp, PinnedReply, SavedPlan } from "@/types";

export function TrackingManager() {
  const { byId } = useAgents();
  const { t } = usePrefs();
  const agentName = useAgentName();
  const name = (slug: string) => agentName(byId(slug), slug);
  const pinned = useApi<PinnedReply[]>("/conversations/pinned");
  const followups = useApi<FollowUp[]>("/followups?status=pending");
  const plans = useApi<SavedPlan[]>("/plans");
  const checkins = useApi<CheckIn[]>("/checkins");
  const [err, setErr] = useState<string | null>(null);

  async function act(fn: () => Promise<unknown>, refresh: () => void) {
    setErr(null);
    try {
      await fn();
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "That didn't work. Please try again.");
    }
  }

  const upcoming = (followups.data ?? []).slice().sort((a, b) => a.due_on.localeCompare(b.due_on));
  const activePlans = (plans.data ?? []).filter((p) => p.status === "active");
  const finishedPlans = (plans.data ?? []).filter((p) => p.status !== "active");

  return (
    <div className="anim-fade journal-page goals-page">
      <PageHeader
        eyebrow={t("plans.eyebrow")}
        title={t("plans.title")}
        lede={t("plans.lede")}
        action={
          <Link href="/week" className="btn btn-sun shrink-0">
            {t("plans.weekLink")}
          </Link>
        }
      />
      {err && (
        <div className="mb-5">
          <ErrorNote message={err} />
        </div>
      )}

      <SectionLabel
        action={
          upcoming.length > 0 ? (
            <a
              href={`${API_BASE}/followups/calendar.ics`}
              className="inline-flex min-h-11 items-center gap-1.5 text-[13px] font-bold underline decoration-pink decoration-2 underline-offset-4"
            >
              <Icon name="calendar" size={16} /> {t("plans.addToCalendar")}
            </a>
          ) : undefined
        }
      >
        {t("plans.comingUp")}
      </SectionLabel>
      {followups.loading && <Spinner />}
      {followups.error && <ErrorNote message={t("plans.followupsError", { error: followups.error })} />}
      {!followups.loading && !followups.error && upcoming.length === 0 && (
        <EmptyState title={t("plans.nothingDated")}>{t("plans.nothingDatedHelp")}</EmptyState>
      )}
      <ul className="mb-11 flex flex-col gap-2.5">
        {upcoming.map((f) => {
          // A trip spans days: it is under way until its last day, then over.
          const passed = daysFromToday(f.ends_on ?? f.due_on) < 0;
          const underway = !passed && daysFromToday(f.due_on) < 0;
          const badge = underway ? t("time.happeningNow") : when(f.due_on);
          return (
            <li key={f.id}>
              <div className="goal-card flex items-center gap-3 border-2 border-ink bg-paper-hi px-3 py-2.5 shadow-pop-xs">
                <button
                  onClick={() =>
                    act(
                      () => apiFetch(`/followups/${f.id}`, { method: "PATCH", body: JSON.stringify({ status: "done" }) }),
                      followups.refetch,
                    )
                  }
                  aria-label={t("plans.markDone", { title: f.title })}
                  className="grid h-11 w-11 shrink-0 place-items-center rounded-full border-2 border-ink bg-paper-hi text-transparent transition hover:bg-sun-pale hover:text-ink-faint"
                >
                  <Icon name="check" size={19} strokeWidth={3} />
                </button>
                <span className="min-w-0 flex-1">
                  <span className="block text-[15px] font-semibold leading-snug text-ink" dir="auto">{f.title}</span>
                  <span className="mt-0.5 block text-[11.5px] font-bold uppercase tracking-wide text-ink-faint">
                    {day(f.due_on)}
                    {f.ends_on && ` – ${day(f.ends_on)}`} · {passed ? t("plans.howDidItGo") : badge} · {name(f.agent_id)}
                  </span>
                </span>
                <span
                  className={`shrink-0 border-2 border-ink px-2 py-0.5 text-[11.5px] font-black uppercase tracking-wide ${
                    passed ? "bg-paper-lo text-ink" : daysFromToday(f.due_on) <= 3 ? "bg-pink text-ink" : "bg-sun text-ink"
                  }`}
                >
                  {passed ? when(f.ends_on ?? f.due_on) : badge}
                </span>
                <button
                  onClick={() =>
                    act(
                      () => apiFetch(`/followups/${f.id}`, { method: "PATCH", body: JSON.stringify({ status: "dismissed" }) }),
                      followups.refetch,
                    )
                  }
                  className="btn-icon !h-11 !w-11 shrink-0 hover:!bg-pink hover:!text-ink"
                  aria-label={t("plans.stopFollowing", { title: f.title })}
                >
                  <Icon name="x" size={17} />
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      <SectionLabel>{t("plans.saved")}</SectionLabel>
      {plans.loading && <Spinner />}
      {plans.error && <ErrorNote message={t("plans.plansError", { error: plans.error })} />}
      {!plans.loading && !plans.error && activePlans.length === 0 && (
        <EmptyState title={t("plans.noPlans")}>{t("plans.noPlansHelp")}</EmptyState>
      )}
      <ul className="mb-11 flex flex-col gap-5">
        {activePlans.map((p) => (
          <li key={p.id}>
            <PlanCard plan={p} owner={name(p.agent_id)} onAct={(fn) => act(fn, plans.refetch)} />
          </li>
        ))}
      </ul>
      {finishedPlans.length > 0 && (
        <div className="mb-11">
          <SectionLabel>{t("plans.finished")}</SectionLabel>
          <ul className="flex flex-col gap-2.5 opacity-70">
            {finishedPlans.map((p) => (
              <li key={p.id}>
                <PlanCard plan={p} owner={name(p.agent_id)} onAct={(fn) => act(fn, plans.refetch)} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <SectionLabel>{t("plans.savedReplies")}</SectionLabel>
      {pinned.loading && <Spinner />}
      {pinned.error && <ErrorNote message={t("plans.savedError", { error: pinned.error })} />}
      {!pinned.loading && !pinned.error && (pinned.data ?? []).length === 0 && (
        <EmptyState title={t("plans.noSavedReplies")}>{t("plans.savedRepliesHelp")}</EmptyState>
      )}
      <ul className="mb-11 flex flex-col gap-4">
        {(pinned.data ?? []).map((p) => (
          <li key={p.message_id}>
            <SavedReply
              reply={p}
              owner={name(p.agent_id)}
              onRemove={() =>
                act(
                  () =>
                    apiFetch(`/conversations/${p.conversation_id}/messages/${p.message_id}`, {
                      method: "PATCH",
                      body: JSON.stringify({ pinned: false }),
                    }),
                  pinned.refetch,
                )
              }
            />
          </li>
        ))}
      </ul>

      <SectionLabel>{t("plans.logged")}</SectionLabel>
      {checkins.loading && <Spinner />}
      {checkins.error && <ErrorNote message={t("plans.checkinsError", { error: checkins.error })} />}
      {!checkins.loading && !checkins.error && (checkins.data ?? []).length === 0 && (
        <EmptyState title={t("plans.nothingLogged")}>{t("plans.nothingLoggedHelp")}</EmptyState>
      )}
      <ul className="flex flex-col divide-y-2 divide-ink border-2 border-ink bg-paper-hi">
        {(checkins.data ?? []).slice(0, 30).map((c) => (
          <li key={c.id} className="flex items-center gap-3 px-3 py-2.5">
            <span className="min-w-0 flex-1">
              <span className="block text-[14.5px] font-semibold leading-snug text-ink" dir="auto">
                {c.text}
                {c.amount !== null && (
                  <span className="text-ink-soft"> · {c.amount}{c.unit ? ` ${c.unit}` : ""}</span>
                )}
              </span>
              <span className="mt-0.5 block text-[11.5px] font-bold uppercase tracking-wide text-ink-faint">
                {day(c.logged_on)} · {name(c.agent_id)}
              </span>
            </span>
            <button
              onClick={() => act(() => apiFetch(`/checkins/${c.id}`, { method: "DELETE" }), checkins.refetch)}
              className="btn-icon !h-11 !w-11 shrink-0 hover:!bg-pink hover:!text-ink"
              aria-label={t("plans.deleteItem", { title: c.text })}
            >
              <Icon name="trash" size={17} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PlanCard({
  plan,
  owner,
  onAct,
}: {
  plan: SavedPlan;
  owner: string;
  onAct: (fn: () => Promise<unknown>) => void;
}) {
  const [open, setOpen] = useState(plan.status === "active");
  const next = plan.steps.find((s) => !s.done);
  const behind = next?.due_on ? daysFromToday(next.due_on) < 0 : false;
  const hasDates = plan.steps.some((s) => s.due_on && !s.done);
  const { t } = usePrefs();

  return (
    <div className="goal-card border-2 border-ink bg-paper-hi shadow-pop-xs">
      <div className="flex flex-wrap items-center gap-3 px-3 py-2.5">
        <button
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="min-w-[12rem] flex-1 text-start"
        >
          <span className="block text-[15px] font-semibold leading-snug text-ink" dir="auto">{plan.title}</span>
          <span className="mt-0.5 block text-[11.5px] font-bold uppercase tracking-wide text-ink-faint">
            {t("plans.progress", { done: plan.done, total: plan.steps.length, owner })}
            {behind && t("plans.notTicked")}
          </span>
        </button>
        {behind && (
          <button
            onClick={() => onAct(() => shiftPlan(plan))}
            className="btn !min-h-[40px] shrink-0 !text-[13px]"
          >
            {t("plans.startAgain")}
          </button>
        )}
        <button
          onClick={() => onAct(() => apiFetch(`/plans/${plan.id}`, { method: "DELETE" }))}
          className="btn-icon !h-11 !w-11 shrink-0 hover:!bg-pink hover:!text-ink"
          aria-label={t("plans.deletePlan", { title: plan.title })}
        >
          <Icon name="trash" size={17} />
        </button>
      </div>
      {open && (
        <div className="border-t-2 border-ink px-3 py-2.5">
          <ul className="flex flex-col gap-1.5">
            {plan.steps.map((s) => (
              <li key={s.id}>
                <label className="flex min-h-11 cursor-pointer items-start gap-3 py-1">
                  <input
                    type="checkbox"
                    checked={s.done}
                    onChange={() =>
                      onAct(() =>
                        apiFetch(`/plans/${plan.id}/steps/${s.id}`, {
                          method: "PATCH",
                          body: JSON.stringify({ done: !s.done }),
                        }),
                      )
                    }
                    className="mt-1 h-5 w-5 shrink-0 accent-pink"
                  />
                  <span dir="auto" className={`text-[14.5px] leading-snug ${s.done ? "text-ink-soft line-through" : "text-ink"}`}>
                    {s.text}
                    {s.due_on && !s.done && (
                      <span className="ms-2 text-[11.5px] font-bold uppercase tracking-wide text-ink-faint">
                        {day(s.due_on)}
                      </span>
                    )}
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {hasDates && (
            <a
              href={`${API_BASE}/plans/${plan.id}/calendar.ics`}
              className="mt-2 inline-flex min-h-11 items-center gap-1.5 text-[13px] font-bold underline decoration-pink decoration-2 underline-offset-4"
            >
              <Icon name="calendar" size={16} /> {t("plans.calendarSteps")}
            </a>
          )}
        </div>
      )}
    </div>
  );
}

/** A reply saved from a chat: the start shown, the rest a click away. */
function SavedReply({ reply, owner, onRemove }: { reply: PinnedReply; owner: string; onRemove: () => void }) {
  const { t } = usePrefs();
  const [open, setOpen] = useState(false);
  const long = reply.content.length > 600;
  return (
    <div className="goal-card border-2 border-ink bg-paper-hi shadow-pop-xs">
      <div className="flex items-center gap-3 px-3 py-2.5">
        <AgentBadge slug={reply.agent_id} size={34} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14.5px] font-semibold text-ink" dir="auto">
            {reply.title}
          </span>
          <span className="block text-[11.5px] font-bold uppercase tracking-wide text-ink-faint">
            {owner} · {relativeTime(reply.pinned_at)}
          </span>
        </span>
        <Link
          href={`/agents/${reply.agent_id}?c=${reply.conversation_id}&m=${reply.message_id}`}
          className="btn !min-h-[40px] shrink-0 !text-[13px]"
        >
          {t("plans.openChat")}
        </Link>
        <button
          onClick={onRemove}
          className="btn-icon !h-11 !w-11 shrink-0 hover:!bg-pink hover:!text-ink"
          aria-label={t("plans.unsave", { title: reply.title })}
        >
          <Icon name="x" size={17} />
        </button>
      </div>
      <div className="border-t-2 border-ink px-4 py-3">
        <div className={`prose-ink text-[14.5px] ${!open && long ? "max-h-40 overflow-hidden" : ""}`}>
          {renderMarkdown(reply.content)}
        </div>
        {long && (
          <button
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            className="mt-2 text-[13px] font-bold underline decoration-pink decoration-2 underline-offset-4"
          >
            {open ? t("plans.showLess") : t("plans.showAll")}
          </button>
        )}
      </div>
    </div>
  );
}

/** Move the plan's start so the next unfinished step falls today. */
async function shiftPlan(plan: SavedPlan) {
  const next = plan.steps.find((s) => !s.done && s.due_on);
  if (!next?.due_on) return;
  const late = -daysFromToday(next.due_on);
  const [y, m, d] = plan.starts_on.split("-").map(Number);
  const start = new Date(y, m - 1, d + late);
  const iso = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, "0")}-${String(start.getDate()).padStart(2, "0")}`;
  await apiFetch(`/plans/${plan.id}`, { method: "PATCH", body: JSON.stringify({ starts_on: iso }) });
}
