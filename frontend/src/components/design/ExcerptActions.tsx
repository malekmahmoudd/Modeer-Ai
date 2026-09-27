"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Drawer } from "./Drawer";
import { PocketCard } from "./PocketCard";
import { useDesignText } from "./text";
import { plainText } from "@/components/chat/MessageActions";
import { useAgents } from "@/features/agents/useAgents";
import { useAgentName } from "@/lib/i18n/agents";
import { usePrefs } from "@/lib/i18n";
import { apiFetch } from "@/lib/api";
import { stageDraft } from "@/lib/design";
import type { Message } from "@/types";
export function ExcerptActions({
  message,
  conversationId,
  agentId,
  agentName,
  onDraft,
  allowSave
}: {
  message: Message;
  conversationId: string;
  agentId: string;
  agentName: string;
  onDraft: (text: string) => void;
  allowSave: boolean;
}) {
  const t = useDesignText();
  const {
    locale
  } = usePrefs();
  const {
    agents
  } = useAgents();
  const name = useAgentName();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [excerpt, setExcerpt] = useState("");
  const [card, setCard] = useState(false);
  const [target, setTarget] = useState(agentId === "modeer" ? "study" : "modeer");
  const [language, setLanguage] = useState(locale === "ar" ? "English" : "العربية");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  function begin(pocket = false) {
    const selection = window.getSelection();
    const root = document.getElementById(`m-${message.id}`)?.querySelector(".prose-ink");
    const text = selection?.rangeCount && root?.contains(selection.anchorNode) && root.contains(selection.focusNode) ? selection.toString().trim() : "";
    setExcerpt((text || plainText(message.content)).slice(0, 8000));
    setErr("");
    setSaved(false);
    setCard(pocket);
    setOpen(!pocket);
  }
  function draft(kind: "explain" | "translate") {
    const quote = excerpt.split("\n").map(s => `> ${s}`).join("\n");
    onDraft(`${kind === "explain" ? locale === "ar" ? "اشرح هذا المقتطف:" : "Explain this excerpt:" : locale === "ar" ? `ترجم هذا المقتطف إلى ${language}:` : `Translate this excerpt into ${language}:`}\n\n${quote}`);
    setOpen(false);
  }
  return <>
    <div className="design-actions reply-actions"><button className="chip" onMouseDown={e => e.preventDefault()} onClick={() => begin()}>{t("select")}</button><button className="chip" onMouseDown={e => e.preventDefault()} onClick={() => begin(true)}>{t("pocket")}</button></div>
    {open && <Drawer title={t("select")} onClose={() => setOpen(false)}><p className="mb-4 text-sm">{t("selectionHelp")}</p><label>{t("excerpt")}<textarea className="field mt-2 min-h-48" dir="auto" maxLength={8000} value={excerpt} onChange={e => {
          setExcerpt(e.target.value);
          setSaved(false);
        }} /></label>
      <div className="design-actions"><button className="btn" disabled={!excerpt.trim()} onClick={() => draft("explain")}>{t("explain")}</button><button className="btn" disabled={!excerpt.trim()} onClick={() => draft("translate")}>{t("translate")}</button><select className="field !w-auto" aria-label={t("target")} value={language} onChange={e => setLanguage(e.target.value)}><option>العربية</option><option>English</option></select></div>
      <div className="design-actions"><select className="field !w-auto" aria-label={t("pass")} value={target} onChange={e => setTarget(e.target.value)}>{agents.filter(a => a.id !== agentId).map(a => <option key={a.id} value={a.id}>{name(a)}</option>)}</select><button className="btn" disabled={!excerpt.trim() || target === agentId} onClick={() => {
          try {
            stageDraft(`${agentName}:\n${excerpt.split("\n").map(s => `> ${s}`).join("\n")}`);
            router.push(`/agents/${target}?handoff=1`);
            setOpen(false);
          } catch {
            setErr(t("error"));
          }
        }}>{t("pass")}</button></div>
      <div className="design-actions">{allowSave && <button className="btn btn-pink" disabled={busy || saved || !excerpt.trim()} onClick={async () => {
          setBusy(true);
          setErr("");
          try {
            const c = await apiFetch<{
              messages: Message[];
            }>(`/conversations/${conversationId}`);
            const old = c.messages.find(m => m.id === message.id)?.meta.design?.excerpts ?? [];
            await apiFetch(`/conversations/${conversationId}/messages/${message.id}/design`, {
              method: "PATCH",
              body: JSON.stringify({
                excerpts: Array.from(new Set([...old, excerpt]))
              })
            });
            setSaved(true);
          } catch {
            setErr(t("error"));
          } finally {
            setBusy(false);
          }
        }}>{t(saved ? "saved" : "savedExcerpt")}</button>}<button className="btn" disabled={!excerpt.trim()} onClick={() => {
          setOpen(false);
          setCard(true);
        }}>{t("pocket")}</button></div>{err && <p role="alert">{err}</p>}
    </Drawer>}
    {card && <PocketCard text={excerpt} author={agentName} onClose={() => setCard(false)} />}
  </>;
}
