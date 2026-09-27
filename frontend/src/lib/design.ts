"use client";

import { apiFetch } from "@/lib/api";
import type { UserProfile } from "@/types";
export interface DesignPreferences {
  front_desk?: string[];
  reading_size?: number;
  reading_spacing?: number;
  reading_width?: number;
  /** Teammates left off Home, Team and the pickers. */
  hidden_agents?: string[];
  text_scale?: number;
  high_contrast?: boolean;
  reduce_motion?: boolean;
  /** Read replies with the server's natural voices instead of the device's. */
  natural_voice?: boolean;
  /** The hour (their time) the daily reminder arrives. */
  push_hour?: number;
  /** Put what is due in the notification, or only a count. */
  push_details?: boolean;
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
