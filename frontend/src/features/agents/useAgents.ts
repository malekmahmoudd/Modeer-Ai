"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import type { Agent, UserProfile } from "@/types";

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

// Teammates the person hid (Account > Teammates): left out of pickers.
let hiddenCache: Promise<string[]> | null = null;

/** Called after the choice changes, so pickers opened later see it. */
export function forgetHiddenAgents() {
  hiddenCache = null;
}

export function useHiddenAgents(): string[] {
  const [hidden, setHidden] = useState<string[]>([]);
  useEffect(() => {
    let on = true;
    hiddenCache ??= apiFetch<UserProfile>("/users/me")
      .then((me) => me.ui_preferences?.hidden_agents ?? [])
      .catch(() => []);
    hiddenCache.then((ids) => on && setHidden(ids));
    return () => {
      on = false;
    };
  }, []);
  return hidden;
}
