"use client";

import { useState } from "react";

import { VoiceButton } from "@/components/chat/VoiceButton";
import { Spinner } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch } from "@/lib/api";
import { calendarDay } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";

interface Proposal {
  checkins: { agent_id: string; text: string; amount: number | null; unit: string | null; details: Record<string, unknown> | null }[];
  followups: { agent_id: string; title: string; due_on: string; ends_on: string | null }[];
  held_back: number;
}

/**
 * Say or type a quick note ("ran 5 km, dentist on Thursday"); the team finds
 * the check-ins and dated follow-ups in it, and only the ones ticked are
 * saved. Nothing is kept until "Save".
 */
export function QuickCapture({ onSaved }: { onSaved: () => void }) {
  const { t, tn } = usePrefs();
  const { byId } = useAgents();
  const agentName = useAgentName();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<"" | "reading" | "saving">("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [found, setFound] = useState<Proposal | null>(null);
  const [ticked, setTicked] = useState<Set<string>>(new Set());

  async function read() {
    setBusy("reading");
    setError("");
    setNotice("");
    try {
      const result = await apiFetch<Proposal>("/capture", { method: "POST", body: JSON.stringify({ text }) });
      setFound(result);
      setTicked(new Set([...result.checkins.map((_, i) => `c${i}`), ...result.followups.map((_, i) => `f${i}`)]));
      if (!result.checkins.length && !result.followups.length) setNotice(t("capture.nothing"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.failed"));
    } finally {
      setBusy("");
    }
  }

  async function save() {
    if (!found) return;
    setBusy("saving");
    setError("");
    let saved = 0;
    try {
      for (const [i, c] of found.checkins.entries()) {
        if (!ticked.has(`c${i}`)) continue;
        await apiFetch("/checkins", { method: "POST", body: JSON.stringify(c) });
        saved += 1;
      }
      for (const [i, f] of found.followups.entries()) {
        if (!ticked.has(`f${i}`)) continue;
        await apiFetch("/followups", { method: "POST", body: JSON.stringify(f) });
        saved += 1;
      }
      setFound(null);
      setText("");
      setNotice(tn("capture.saved", saved));
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.failed"));
      onSaved();
    } finally {
      setBusy("");
    }
  }

  function toggle(key: string) {
    const next = new Set(ticked);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setTicked(next);
  }

  return (
    <section className="mb-8 border-2 border-ink bg-paper-hi p-4 shadow-pop-xs" aria-labelledby="capture-title">
      <h2 id="capture-title" className="display text-[20px]">{t("capture.title")}</h2>
      <p className="mb-3 mt-1 text-[14px] text-ink-soft">{t("capture.help")}</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim().length >= 3 && !busy) void read();
        }}
      >
        <div className="flex items-end gap-2">
          <label htmlFor="capture-text" className="sr-only">{t("capture.title")}</label>
          <textarea
            id="capture-text"
            dir="auto"
            rows={2}
            maxLength={2000}
            className="field min-h-[60px] flex-1"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={t("capture.placeholder")}
          />
          <VoiceButton
            disabled={!!busy}
            onText={(heard) => setText((current) => (current.trim() ? `${current.trimEnd()} ${heard}` : heard))}
            onError={setError}
          />
        </div>
        <button className="btn btn-sun mt-3" disabled={!!busy || text.trim().length < 3}>
          {busy === "reading" ? <Spinner /> : null} {t("capture.find")}
        </button>
      </form>
      {error && <p role="alert" className="mt-3 font-semibold text-pink-deep">{error}</p>}
      {notice && <p role="status" className="mt-3 font-semibold">{notice}</p>}
      {found && (found.checkins.length > 0 || found.followups.length > 0) && (
        <div className="mt-4 border-t-2 border-ink/15 pt-3">
          <p className="mb-2 font-bold">{t("capture.confirm")}</p>
          <ul className="space-y-1.5">
            {found.checkins.map((c, i) => (
              <li key={`c${i}`}>
                <label className="flex min-h-10 items-center gap-3">
                  <input type="checkbox" className="h-5 w-5 accent-pink" checked={ticked.has(`c${i}`)} onChange={() => toggle(`c${i}`)} />
                  <span dir="auto"><strong>{t("capture.logged")}</strong> {c.text} <span className="text-ink-faint">· {agentName(byId(c.agent_id), c.agent_id)}</span></span>
                </label>
              </li>
            ))}
            {found.followups.map((f, i) => (
              <li key={`f${i}`}>
                <label className="flex min-h-10 items-center gap-3">
                  <input type="checkbox" className="h-5 w-5 accent-pink" checked={ticked.has(`f${i}`)} onChange={() => toggle(`f${i}`)} />
                  <span dir="auto"><strong>{calendarDay(f.due_on)}</strong> {f.title} <span className="text-ink-faint">· {agentName(byId(f.agent_id), f.agent_id)}</span></span>
                </label>
              </li>
            ))}
          </ul>
          {found.held_back > 0 && <p className="mt-2 text-[13px] text-ink-soft">{t("capture.heldBack")}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn btn-pink" disabled={!!busy || ticked.size === 0} onClick={() => void save()}>
              {busy === "saving" ? t("common.saving") : t("capture.save")}
            </button>
            <button className="btn" disabled={!!busy} onClick={() => setFound(null)}>{t("common.cancel")}</button>
          </div>
        </div>
      )}
    </section>
  );
}
