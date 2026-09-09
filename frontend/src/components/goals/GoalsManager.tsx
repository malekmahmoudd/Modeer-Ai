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
  const { data, loading, refetch } = useApi<Goal[]>("/goals");
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState(3);
  const [adding, setAdding] = useState(false);

  const goals = data || [];
  const active = goals.filter((g) => g.status !== "done");
  const done = goals.filter((g) => g.status === "done");

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setAdding(true);
    try {
      await apiFetch("/goals", { method: "POST", body: JSON.stringify({ title, priority }) });
      setTitle("");
      setPriority(3);
      refetch();
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
    <div className="anim-fade-up max-w-2xl">
      <PageHeader
        eyebrow="Goals"
        title="Goals & priorities"
        lede="Modeer and your team use these to shape advice and your daily briefing. Keep it short — a handful of things that actually matter."
      />

      <form onSubmit={add} className="mb-8 flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          className="field flex-1"
          placeholder="What do you want to achieve?"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <div className="flex gap-2">
          <select
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
          <button type="submit" disabled={adding} className="btn-primary shrink-0">
            Add goal
          </button>
        </div>
      </form>

      <SectionLabel>Active</SectionLabel>
      {loading && <Spinner />}
      {!loading && active.length === 0 && (
        <EmptyState title="No active goals">Add one above to get started.</EmptyState>
      )}
      <div className="flex flex-col gap-2">
        {active
          .slice()
          .sort((a, b) => a.priority - b.priority)
          .map((g) => (
            <GoalItem key={g.id} goal={g} onPatch={patch} onRemove={remove} />
          ))}
      </div>

      {done.length > 0 && (
        <div className="mt-10">
          <SectionLabel>Completed</SectionLabel>
          <div className="flex flex-col gap-2 opacity-55">
            {done.map((g) => (
              <GoalItem key={g.id} goal={g} onPatch={patch} onRemove={remove} />
            ))}
          </div>
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
  const isTop = goal.priority <= 1;
  return (
    <div className="card group flex items-center gap-3 px-3.5 py-2.5">
      <button
        onClick={() => onPatch(goal.id, { status: done ? "active" : "done" })}
        className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border transition ${
          done
            ? "border-emerald-400/40 bg-emerald-400/20 text-emerald-300"
            : "border-line-strong text-transparent hover:border-content-dim hover:text-content-faint"
        }`}
        aria-label="Toggle complete"
      >
        <Icon name="check" size={12} />
      </button>
      <span
        className={`min-w-0 flex-1 text-[13.5px] ${done ? "text-content-dim line-through" : "text-white/90"}`}
      >
        {goal.title}
      </span>
      <span
        className="tag shrink-0"
        style={
          isTop && !done
            ? { borderColor: "rgba(251,191,36,0.3)", color: "#fcd34d", background: "rgba(251,191,36,0.08)" }
            : undefined
        }
      >
        {label}
      </span>
      <button
        onClick={() => onRemove(goal.id)}
        className="grid h-7 w-7 shrink-0 place-items-center rounded-[8px] text-content-faint opacity-40 transition hover:text-red-300 group-hover:opacity-100"
        aria-label="Delete goal"
      >
        <Icon name="trash" size={14} />
      </button>
    </div>
  );
}
