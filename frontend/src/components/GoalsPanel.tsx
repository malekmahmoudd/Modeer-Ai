"use client";

import Link from "next/link";

import { useApi } from "@/lib/api";
import type { Goal } from "@/types";

const PRIORITY_LABEL = ["", "Top", "High", "Medium", "Low", "Someday"];

export function GoalsPanel() {
  const { data, loading } = useApi<Goal[]>("/goals?status=active");
  const goals = (data || []).slice(0, 4);

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-white">Current goals</p>
        <Link href="/goals" className="text-[11px] text-white/40 hover:text-white/80">
          Manage →
        </Link>
      </div>

      {loading && <p className="mt-4 text-sm text-white/40">Loading…</p>}

      {!loading && goals.length === 0 && (
        <p className="mt-4 text-sm text-white/45">
          No goals yet. Add a few so your whole team knows what matters —{" "}
          <Link href="/goals" className="text-white/70 underline">
            add one
          </Link>
          .
        </p>
      )}

      <ul className="mt-4 flex flex-col gap-2">
        {goals.map((goal) => (
          <li
            key={goal.id}
            className="flex items-center gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3.5 py-2.5"
          >
            <span
              className={`chip ${
                goal.priority <= 1 ? "!border-amber-400/30 !text-amber-200" : ""
              }`}
            >
              {PRIORITY_LABEL[goal.priority] || "—"}
            </span>
            <span className="truncate text-sm text-white/80">{goal.title}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
