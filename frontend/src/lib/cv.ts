/** The CV builder's data, and the checks it runs on each bullet. */

export interface Role {
  title: string;
  organisation: string;
  place: string;
  start: string;
  end: string;
  bullets: string[];
}

export interface Study {
  qualification: string;
  institution: string;
  start: string;
  end: string;
  note: string;
}

export interface CvData {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
  summary: string;
  experience: Role[];
  education: Study[];
  skills: string[];
  languages: string[];
}

export interface Cv {
  id: string;
  title: string;
  target_role: string | null;
  data: CvData;
  updated_at: string;
}

export const EMPTY_ROLE: Role = { title: "", organisation: "", place: "", start: "", end: "", bullets: [] };
export const EMPTY_STUDY: Study = { qualification: "", institution: "", start: "", end: "", note: "" };

export type BulletIssue = "verb" | "number" | "long" | "short";

// Openings that describe a duty rather than what was achieved.
const WEAK = /^(responsible|helped|assisted|worked|was|were|did|involved|participated|handled|tasked|duties|in charge|مسؤول|مسؤولة|ساعدت|ساهمت|شاركت|عملت|كنت|كان|قمت)\b/i;

/** What would make a bullet stronger: an action verb first, a number showing
 *  the result, and one line's length. */
export function checkBullet(bullet: string): BulletIssue[] {
  const text = bullet.trim();
  if (!text) return [];
  const words = text.split(/\s+/).length;
  const issues: BulletIssue[] = [];
  if (WEAK.test(text)) issues.push("verb");
  if (!/[0-9٠-٩]/.test(text)) issues.push("number");
  if (words > 32 || text.length > 220) issues.push("long");
  else if (words < 5) issues.push("short");
  return issues;
}

/** A list typed as "a, b, c" (Arabic commas too). */
export function splitList(value: string, max: number): string[] {
  return value.split(/[,،\n]/).map((v) => v.trim()).filter(Boolean).slice(0, max);
}
