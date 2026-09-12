"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

/** Pages a signed-out person can use. A 401 there is an answer, not a reason to leave. */
export const PUBLIC_PAGES = ["/login", "/privacy", "/signup", "/recover"];

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * A validation failure arrives as a list of objects, one per field. Turned into
 * the sentences they carry — otherwise a form shows "[object Object]".
 */
function readableDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
      .map((msg) => msg.replace(/^Value error, /, ""))
      .filter(Boolean)
      .join(" ");
  }
  return "";
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });
  if (res.status === 401 && typeof window !== "undefined" && !PUBLIC_PAGES.includes(window.location.pathname)) {
    window.location.assign("/login");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = readableDetail(body.detail) || JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Minimal data hook: fetch on mount, expose loading/error and a refetch. */
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch<T>(path);
      if (mounted.current) setData(result);
    } catch (err) {
      if (mounted.current) {
        setError(err instanceof Error ? err.message : "Request failed");
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, ...deps]);

  return { data, loading, error, refetch: load, setData };
}
