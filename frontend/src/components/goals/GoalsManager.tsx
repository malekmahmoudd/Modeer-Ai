"use client";

import { useState } from "react";

import { EmptyState, SectionHeading, Spinner } from "@/components/ui/primitives";
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
  const [detail, setDetail] = useState("");
  const [priority, setPriority] = useState(3);

  const goals = data || [];
  const active = goals.filter((g) => g.status !== "done");
  const done = goals.filter((g) => g.status === "done");

  async function addGoal(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    await apiFetch("/goals", {
      method: "POST",
      body: JSON.stringify({ title, detail, priority }),
    });
    setTitle("");
    setDetail("");
    setPriority(3);
    refetch();
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
    <div className="mx-auto max-w-3xl animate-fade-up">
      <div className="mb-8">
        <p className="text-sm text-white/40">Goals</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">
          Goals & priorities
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-white/50">
          Your team uses these to shape advice and your daily briefing.
        </p>
      </div>

      <form onSubmit={addGoal} className="card mb-8 flex flex-col gap-3 p-5">
        <input
          className="input"
          placeholder="What do you want to achieve?"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <textarea
          className="input min-h-[60px]"
          placeholder="Any detail or context (optional)"
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
        />
        <div className="flex items-center gap-3">
          <select
            className="input !w-auto"
            value={priority}
            onChange={(e) => setPriority(Number(e.target.value))}
          >
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label} priority
              </option>
            ))}
          </select>
          <button type="submit" className="btn-primary ml-auto">
            Add goal
          </button>
        </div>
      </form>

      <SectionHeading title="Active" />
      {loading && <Spinner />}
      {!loading && active.length === 0 && (
        <EmptyState title="No active goals">Add one above to get started.</EmptyState>
      )}
      <div className="flex flex-col gap-2">
        {active.map((g) => (
          <GoalItem key={g.id} goal={g} onPatch={patch} onRemove={remove} />
        ))}
      </div>

      {done.length > 0 && (
        <div className="mt-10">
          <SectionHeading title="Completed" />
          <div className="flex flex-col gap-2 opacity-60">
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
  const isDone = goal.status === "done";
  return (
    <div className="card flex items-start gap-3 p-4">
      <button
        onClick={() => onPatch(goal.id, { status: isDone ? "active" : "done" })}
        className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md border text-xs ${
          isDone
            ? "border-emerald-400/40 bg-emerald-400/20 text-emerald-300"
            : "border-white/20 text-transparent hover:border-white/40"
        }`}
        aria-label="Toggle complete"
      >
        ✓
      </button>
      <div className="min-w-0 flex-1">
        <p className={`text-sm font-medium text-white/85 ${isDone ? "line-through" : ""}`}>
          {goal.title}
        </p>
        {goal.detail && <p className="mt-0.5 text-xs text-white/45">{goal.detail}</p>}
      </div>
      <span className="chip">{label}</span>
      <button
        onClick={() => onRemove(goal.id)}
        className="text-white/25 hover:text-red-300"
        aria-label="Delete goal"
      >
        ✕
      </button>
    </div>
  );
}
