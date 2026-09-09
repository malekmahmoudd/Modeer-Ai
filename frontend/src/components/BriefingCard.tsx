"use client";

import Link from "next/link";
import { useState } from "react";

import { Spinner } from "@/components/ui/primitives";
import { apiFetch, useApi } from "@/lib/api";
import type { Briefing } from "@/types";

export function BriefingCard() {
  const { data, loading, error, setData } = useApi<Briefing>("/briefings/today");
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    setRefreshing(true);
    try {
      setData(await apiFetch<Briefing>("/briefings/today?refresh=true"));
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="card relative overflow-hidden p-6">
      <div
        className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full opacity-40 blur-3xl"
        style={{ background: "radial-gradient(circle, rgba(124,58,237,0.5), transparent 70%)" }}
      />
      <div className="flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 text-sm">
          🧭
        </span>
        <p className="text-sm font-semibold text-white">Today&apos;s briefing from Modeer</p>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="ml-auto text-[11px] text-white/40 hover:text-white/80"
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {loading && (
        <div className="mt-4 flex items-center gap-2 text-sm text-white/40">
          <Spinner /> Preparing your briefing…
        </div>
      )}
      {error && <p className="mt-4 text-sm text-red-300">{error}</p>}

      {data && (
        <div className="mt-4">
          <p className="text-sm leading-relaxed text-white/70">{data.summary}</p>
          <ul className="mt-4 flex flex-col gap-2">
            {data.items.map((item, i) => (
              <li
                key={i}
                className="flex items-start gap-3 rounded-xl border border-white/[0.05] bg-white/[0.02] px-3.5 py-2.5 text-sm text-white/75"
              >
                <span className="text-base leading-none">{item.icon}</span>
                <span>{item.text}</span>
              </li>
            ))}
          </ul>
          <Link
            href="/agents/modeer"
            className="btn-ghost mt-4 w-full sm:w-auto"
          >
            Plan today with Modeer
          </Link>
        </div>
      )}
    </div>
  );
}
