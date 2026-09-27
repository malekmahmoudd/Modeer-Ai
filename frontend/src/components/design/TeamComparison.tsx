"use client";

import { useEffect, useState } from "react";
import { Drawer } from "./Drawer";
import { useDesignText } from "./text";
import { apiFetch } from "@/lib/api";
import { renderMarkdown } from "@/lib/markdown";
import { useAgents } from "@/features/agents/useAgents";
import { useAgentName } from "@/lib/i18n/agents";
import type { ConversationDetail, Message } from "@/types";
export function TeamComparison({
  conversationId
}: {
  conversationId: string;
}) {
  const t = useDesignText();
  const {
    byId
  } = useAgents();
  const name = useAgentName();
  const [open, setOpen] = useState(false);
  const [takes, setTakes] = useState<{
    agent: string;
    answer: string;
  }[]>([]);
  const [msg, setMsg] = useState<Message | null>(null);
  const [tradeoffs, setTradeoffs] = useState("");
  const [choice, setChoice] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (!open) return;
    let active = true;
    (async () => {
      try {
        const c = await apiFetch<ConversationDetail>(`/conversations/${conversationId}`);
        const m = c.messages.find(m => m.meta.team);
        if (!m) throw new Error(t("legacy"));
        const rows = await Promise.all(m.meta.team!.map(async r => {
          try {
            const d = await apiFetch<ConversationDetail>(`/conversations/${r.conversation_id}`);
            return {
              agent: r.agent_id,
              answer: d.messages.find(m => m.role === "assistant")?.content ?? ""
            };
          } catch {
            return {
              agent: r.agent_id,
              answer: t("legacy")
            };
          }
        }));
        if (active) {
          setMsg(m);
          setTakes(rows);
          setTradeoffs(m.meta.design?.tradeoffs ?? "");
          setChoice(m.meta.design?.choice ?? "");
        }
      } catch (e) {
        if (active) setErr(e instanceof Error ? e.message : t("error"));
      }
    })();
    return () => {
      active = false;
    };
    // Labels do not change while this request is in flight.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, conversationId]);
  return <><button className="btn mt-3" onClick={() => {
      setMsg(null);
      setErr("");
      setSaved(false);
      setOpen(true);
    }}>{t("compare")}</button>{open && <Drawer title={t("compare")} onClose={() => setOpen(false)}><p className="mb-4 text-sm">{t("compareHelp")}</p>{err && <p role="alert">{err}</p>}{!msg && !err && <p role="status">{t("loading")}</p>}{msg && <><div className="grid gap-3 sm:grid-cols-2">{takes.map(r => <section key={r.agent} className="sheet p-3"><h3 className="mb-3 font-black">{name(byId(r.agent), r.agent)}</h3><div className="prose-ink">{renderMarkdown(r.answer)}</div></section>)}</div><label className="my-4 block font-bold">{t("tradeoffs")}<textarea className="field mt-2 min-h-28" dir="auto" maxLength={4000} value={tradeoffs} onChange={e => {
            setTradeoffs(e.target.value);
            setSaved(false);
          }} /></label><label className="mb-4 block font-bold">{t("choice")}<textarea className="field mt-2" dir="auto" maxLength={2000} value={choice} onChange={e => {
            setChoice(e.target.value);
            setSaved(false);
          }} /></label><button className="btn btn-pink" disabled={busy} onClick={async () => {
          setBusy(true);
          setErr("");
          try {
            await apiFetch(`/conversations/${conversationId}/messages/${msg.id}/design`, {
              method: "PATCH",
              body: JSON.stringify({
                tradeoffs,
                choice
              })
            });
            setSaved(true);
          } catch {
            setErr(t("error"));
          } finally {
            setBusy(false);
          }
        }}>{t(saved ? "saved" : "save")}</button></>}</Drawer>}</>;
}
