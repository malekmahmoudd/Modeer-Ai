"use client";

import { apiFetch } from "@/lib/api";
import type { UserProfile } from "@/types";
export interface DesignPreferences {
  front_desk?: string[];
  reading_size?: number;
  reading_spacing?: number;
  reading_width?: number;
}
export const DEFAULT_DESK = ["study", "career", "research", "writing"];
export function savePreferences(patch: DesignPreferences) {
  return apiFetch<UserProfile>("/users/me", {
    method: "PATCH",
    body: JSON.stringify({
      ui_preferences: patch
    })
  });
}
/** Text travels only within this tab, never in a URL. Throws visibly if storage is unavailable. */
export function stageDraft(text: string) {
  sessionStorage.setItem("fareeq.handoff", text);
}
export function escapeHTML(text: string) {
  return text.replace(/[&<>"']/g, c => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[c]!);
}
