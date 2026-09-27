"use client";

import { useState } from "react";
import { AgentPanel } from "@/components/AgentPanel";
import { Drawer } from "@/components/design/Drawer";
import { useDesignText } from "@/components/design/text";
import { useApi } from "@/lib/api";
import { DEFAULT_DESK, savePreferences } from "@/lib/design";
import { useAgentName } from "@/lib/i18n/agents";
import type { Agent, UserProfile } from "@/types";
export function FrontDesk() {
  const {
    data: agents
  } = useApi<Agent[]>("/agents");
  const {
    data: user,
    setData,
    error,
    loading
  } = useApi<UserProfile>("/users/me");
  const t = useDesignText();
  const name = useAgentName();
  const hidden = user?.ui_preferences?.hidden_agents ?? [];
  const ids = (user?.ui_preferences?.front_desk ?? DEFAULT_DESK).filter(id => !hidden.includes(id));
  const [draft, setDraft] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function save() {
    if (!draft) return;
    setBusy(true);
    setErr("");
    try {
      setData(await savePreferences({
        front_desk: draft
      }));
      setDraft(null);
    } catch {
      setErr(t("error"));
    } finally {
      setBusy(false);
    }
  }
  function move(i: number, offset: number) {
    const next = [...draft!];
    [next[i], next[i + offset]] = [next[i + offset], next[i]];
    setDraft(next);
  }
  return <>
    <div className="mb-4 flex justify-end"><button className="btn" disabled={loading || !!error} onClick={() => {
        setDraft([...ids]);
        setErr("");
      }}>{t("desk")} · {t("customize")}</button></div>
    {error && <p role="alert">{error}</p>}
    {!ids.length && <p className="mb-3">{t("noPins")}</p>}
    <div className="sunshine-team-grid">{ids.map((id, i) => {
        const agent = agents?.find(a => a.id === id);
        return agent ? <AgentPanel key={id} agent={agent} index={i} featured /> : null;
      })}</div>
    {draft && <Drawer title={t("desk")} onClose={() => {
      if (!busy) setDraft(null);
    }}>
      <ol className="space-y-2">{draft.map((id, i) => <li key={id} className="sheet flex flex-wrap items-center gap-2 p-2"><strong className="flex-1">{name(agents?.find(a => a.id === id), id)}</strong><button className="btn" disabled={busy || !i} aria-label={`${t("up")}: ${id}`} onClick={() => move(i, -1)}>{t("up")}</button><button className="btn" disabled={busy || i === draft.length - 1} aria-label={`${t("down")}: ${id}`} onClick={() => move(i, 1)}>{t("down")}</button><button className="btn" disabled={busy} onClick={() => setDraft(draft.filter(x => x !== id))}>{t("unpin")}</button></li>)}</ol>
      <div className="design-actions">{agents?.filter(a => !a.is_assistant && !draft.includes(a.id) && !hidden.includes(a.id)).map(a => <button key={a.id} className="btn" disabled={busy} onClick={() => setDraft([...draft, a.id])}>{t("pin")} {name(a)}</button>)}</div>
      <div className="design-actions"><button className="btn btn-pink" disabled={busy} onClick={save}>{t("save")}</button><button className="btn" disabled={busy} onClick={() => setDraft([...DEFAULT_DESK])}>{t("reset")}</button></div>{err && <p role="alert">{err}</p>}
    </Drawer>}
  </>;
}
