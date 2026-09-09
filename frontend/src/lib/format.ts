export function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function firstName(name?: string | null): string | undefined {
  if (!name || name.toLowerCase() === "you") return undefined;
  return name.trim().split(/\s+/)[0];
}

export function greeting(name?: string): string {
  const h = new Date().getHours();
  const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return name ? `${part}, ${name}` : `${part}`;
}

/** "education.field_of_study" / "weak_topics.weak_topic" -> "Field of study" */
export function humanizeKey(key: string): string {
  const last = key.split(".").pop() || key;
  const s = last.replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export const CATEGORY_LABELS: Record<string, string> = {
  education: "Education",
  career: "Career",
  goals: "Goals & priorities",
  context: "About you",
  finance: "Finance",
  health: "Health",
  preferences: "Preferences",
  weak_topics: "Areas to work on",
  targets: "Targets",
  routine: "Routine",
  general: "General",
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] || humanizeKey(category);
}

export function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((c) => c + c)
          .join("")
      : clean;
  const n = parseInt(full, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Inline CSS custom property so descendants can use var(--accent). */
export function accentStyle(hex: string): React.CSSProperties {
  return {
    ["--accent" as string]: hex,
    ["--accent-soft" as string]: hexToRgba(hex, 0.14),
  } as React.CSSProperties;
}
