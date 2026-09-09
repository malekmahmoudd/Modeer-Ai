"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import type { Agent } from "@/types";

let cache: Agent[] | null = null;
let inflight: Promise<Agent[]> | null = null;

function load(): Promise<Agent[]> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = apiFetch<Agent[]>("/agents").then((a) => {
      cache = a;
      inflight = null;
      return a;
    });
  }
  return inflight;
}

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>(cache || []);
  const [loading, setLoading] = useState(!cache);

  useEffect(() => {
    let on = true;
    load()
      .then((a) => on && setAgents(a))
      .finally(() => on && setLoading(false));
    return () => {
      on = false;
    };
  }, []);

  const byId = (id: string) => agents.find((a) => a.id === id);
  return { agents, byId, loading };
}
