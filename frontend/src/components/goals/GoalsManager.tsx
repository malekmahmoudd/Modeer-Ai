"use client";

import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { EmptyState, PageHeader, SectionLabel, Spinner } from "@/components/ui/primitives";
import { apiFetch, useApi } from "@/lib/api";
import type { Goal } from "@/types";

const PRIORITIES = [
  { value: 1, label: "Top" },
  { value: 2, label: "High" },
  { value: 3, label: "Medium" },
  { value: 4, label: "Low" },
  { value: 5, label: "Someday" },
];

export function GoalsManager() {
  const { data, loading, error, refetch } = useApi<Goal[]>("/goals");
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
      setAddErr(ex instanceof Error ? ex.message : "Couldn't add that goal.");
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
        eyebrow="Your next chapter"
        title="Make room for what matters."
        lede="Modeer and your team use these to shape advice and your daily briefing. Keep it short — a handful of things that actually matter."
      />

      <div className="goal-summary" aria-label="Goal progress"><span><strong>{active.length}</strong> in progress</span><span><strong>{done.length}</strong> completed</span><p className="hand">One step at a time.</p></div>
      <form onSubmit={add} className="goal-form mb-9">
        <div className="flex flex-col gap-2.5 sm:flex-row">
          <label htmlFor="goal-title" className="sr-only">
            What do you want to achieve?
          </label>
          <input
            id="goal-title"
            className="field flex-1"
            placeholder="What do you want to achieve?"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="flex gap-2.5">
            <label htmlFor="goal-priority" className="sr-only">
              Priority
            </label>
            <select
              id="goal-priority"
              className="field !w-auto flex-1"
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value))}
            >
              {PRIORITIES.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={adding || !title.trim()}
              className="btn btn-pink shrink-0"
            >
              {adding ? "Adding…" : "Add goal"}
            </button>
          </div>
        </div>
        {addErr && (
          <p role="alert" className="mt-2 text-[13px] font-bold text-pink-deep">
            {addErr}
          </p>
        )}
      </form>

      <SectionLabel>Active</SectionLabel>
      {loading && <Spinner />}
      {error && (
        <p role="alert" className="border-2 border-ink bg-pink-pale px-3 py-2 text-[14px] font-semibold">
          Couldn&apos;t load your goals: {error}
        </p>
      )}
      {!loading && !error && active.length === 0 && (
        <EmptyState title="No active goals">Add one above to get started.</EmptyState>
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
          <SectionLabel>Completed</SectionLabel>
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
  const label = PRIORITIES.find((p) => p.value === goal.priority)?.label ?? "—";
  const done = goal.status === "done";
  const isTop = goal.priority <= 1 && !done;

  return (
    <div className="goal-card flex items-center gap-3 border-2 border-ink bg-paper-hi px-3 py-2.5 shadow-pop-xs">
      <button
        onClick={() => onPatch(goal.id, { status: done ? "active" : "done" })}
        aria-pressed={done}
        aria-label={done ? `Mark "${goal.title}" as active` : `Mark "${goal.title}" as done`}
        className={`grid h-11 w-11 shrink-0 place-items-center rounded-full border-2 border-ink transition ${
          done ? "bg-sun text-ink" : "bg-paper-hi text-transparent hover:bg-sun-pale hover:text-ink-faint"
        }`}
      >
        <Icon name="check" size={19} strokeWidth={3} />
      </button>

      <span
        className={`min-w-0 flex-1 text-[15px] font-semibold leading-snug ${
          done ? "text-ink-soft line-through" : "text-ink"
        }`}
      >
        {goal.title}
      </span>

      <span
        className={`shrink-0 border-2 border-ink px-2 py-0.5 text-[11.5px] font-black uppercase tracking-wide ${
          isTop ? "bg-pink text-white" : "bg-paper-lo text-ink"
        }`}
      >
        {label}
      </span>

      <button
        onClick={() => onRemove(goal.id)}
        className="btn-icon !h-11 !w-11 shrink-0 hover:!bg-pink hover:!text-white"
        aria-label={`Delete goal "${goal.title}"`}
      >
        <Icon name="trash" size={17} />
      </button>
    </div>
  );
}
