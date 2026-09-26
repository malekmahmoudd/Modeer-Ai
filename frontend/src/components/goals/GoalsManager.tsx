"use client";

import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { EmptyState, PageHeader, SectionLabel, Spinner } from "@/components/ui/primitives";
import { apiFetch, useApi } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";
import type { Goal } from "@/types";

const PRIORITIES = [1, 2, 3, 4, 5].map((value) => ({ value, label: `priority.${value}` as MessageKey }));

export function GoalsManager() {
  const { data, loading, error, refetch } = useApi<Goal[]>("/goals");
  const { t } = usePrefs();
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState(3);
  const [adding, setAdding] = useState(false);
  const [addErr, setAddErr] = useState<string | null>(null);

  const goals = data || [];
  const active = goals.filter((g) => g.status !== "done");
  const done = goals.filter((g) => g.status === "done");

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setAdding(true);
    setAddErr(null);
    try {
      await apiFetch("/goals", { method: "POST", body: JSON.stringify({ title, priority }) });
      setTitle("");
      setPriority(3);
      refetch();
    } catch (ex) {
      setAddErr(ex instanceof Error ? ex.message : t("goals.addError"));
    } finally {
      setAdding(false);
    }
  }

  async function patch(id: string, body: Partial<Goal>) {
    await apiFetch(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(body) });
    refetch();
  }
  async function remove(id: string) {
    await apiFetch(`/goals/${id}`, { method: "DELETE" });
    refetch();
  }

  return (
    <div className="anim-fade journal-page goals-page">
      <PageHeader
        eyebrow={t("goals.eyebrow")}
        title={t("goals.title")}
        lede={t("goals.lede")}
      />

      <div className="goal-summary" role="group" aria-label={t("goals.progress")}><span><strong>{active.length}</strong> {t("goals.inProgress")}</span><span><strong>{done.length}</strong> {t("goals.completed")}</span><p className="hand">{t("goals.note")}</p></div>
      <form onSubmit={add} className="goal-form mb-9">
        <div className="flex flex-col gap-2.5 sm:flex-row">
          <label htmlFor="goal-title" className="sr-only">
            {t("goals.what")}
          </label>
          <input
            id="goal-title"
            dir="auto"
            className="field flex-1"
            placeholder={t("goals.what")}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="flex gap-2.5">
            <label htmlFor="goal-priority" className="sr-only">
              {t("goals.priority")}
            </label>
            <select
              id="goal-priority"
              className="field !w-auto flex-1"
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value))}
            >
              {PRIORITIES.map((p) => (
                <option key={p.value} value={p.value}>
                  {t(p.label)}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={adding || !title.trim()}
              className="btn btn-pink shrink-0"
            >
              {adding ? t("goals.adding") : t("goals.add")}
            </button>
          </div>
        </div>
        {addErr && (
          <p role="alert" className="mt-2 text-[13px] font-bold text-pink-deep">
            {addErr}
          </p>
        )}
      </form>

      <SectionLabel>{t("goals.active")}</SectionLabel>
      {loading && <Spinner />}
      {error && (
        <p role="alert" className="border-2 border-ink bg-pink-pale px-3 py-2 text-[14px] font-semibold">
          {t("goals.loadError", { error })}
        </p>
      )}
      {!loading && !error && active.length === 0 && (
        <EmptyState title={t("goals.none")}>{t("goals.noneHelp")}</EmptyState>
      )}

      <ul className="flex flex-col gap-2.5">
        {active
          .slice()
          .sort((a, b) => a.priority - b.priority)
          .map((g) => (
            <li key={g.id}>
              <GoalItem goal={g} onPatch={patch} onRemove={remove} />
            </li>
          ))}
      </ul>

      {done.length > 0 && (
        <div className="mt-11">
          <SectionLabel>{t("goals.done")}</SectionLabel>
          <ul className="flex flex-col gap-2.5 opacity-70">
            {done.map((g) => (
              <li key={g.id}>
                <GoalItem goal={g} onPatch={patch} onRemove={remove} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function GoalItem({
  goal,
  onPatch,
  onRemove,
}: {
  goal: Goal;
  onPatch: (id: string, body: Partial<Goal>) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}) {
  const { t } = usePrefs();
  const key = PRIORITIES.find((p) => p.value === goal.priority)?.label;
  const label = key ? t(key) : "—";
  const done = goal.status === "done";
  const isTop = goal.priority <= 1 && !done;

  return (
    <div className="goal-card flex items-center gap-3 border-2 border-ink bg-paper-hi px-3 py-2.5 shadow-pop-xs">
      <button
        onClick={() => onPatch(goal.id, { status: done ? "active" : "done" })}
        aria-pressed={done}
        aria-label={t(done ? "goals.markActive" : "goals.markDone", { title: goal.title })}
        className={`grid h-11 w-11 shrink-0 place-items-center rounded-full border-2 border-ink transition ${
          done ? "bg-sun text-ink" : "bg-paper-hi text-transparent hover:bg-sun-pale hover:text-ink-faint"
        }`}
      >
        <Icon name="check" size={19} strokeWidth={3} />
      </button>

      <span
        dir="auto"
        className={`min-w-0 flex-1 text-[15px] font-semibold leading-snug ${
          done ? "text-ink-soft line-through" : "text-ink"
        }`}
      >
        {goal.title}
      </span>

      <span
        className={`shrink-0 border-2 border-ink px-2 py-0.5 text-[11.5px] font-black uppercase tracking-wide ${
          isTop ? "bg-pink text-ink" : "bg-paper-lo text-ink"
        }`}
      >
        {label}
      </span>

      <button
        onClick={() => onRemove(goal.id)}
        className="btn-icon !h-11 !w-11 shrink-0 hover:!bg-pink hover:!text-ink"
        aria-label={t("goals.delete", { title: goal.title })}
      >
        <Icon name="trash" size={17} />
      </button>
    </div>
  );
}
