"use client";

import { useEffect, useState } from "react";
import { Drawer } from "./Drawer";
import { useDesignText, type DesignKey } from "./text";
import { apiFetch } from "@/lib/api";
import type { Message, RetrievedPassage } from "@/types";
export function ReplyDetails({
  message,
  conversationId
}: {
  message: Message;
  conversationId: string;
}) {
  const t = useDesignText();
  const [source, setSource] = useState<RetrievedPassage | null>(null);
  const [context, setContext] = useState(false);
  const [body, setBody] = useState<{
    text: string;
    note: string | null;
    heading: string | null;
  } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!source) return;
    let active = true;
    apiFetch<{
      text: string;
      note: string | null;
      heading: string | null;
    }>(`/conversations/${conversationId}/messages/${message.id}/sources/${source.label}`).then(b => {
      if (active) setBody(b);
    }).catch(e => {
      if (active) setErr(e.message);
    });
    return () => {
      active = false;
    };
  }, [source, conversationId, message.id]);
  const ctx = message.meta?.context;
  return <>
    <div className="design-actions reply-actions">
      {ctx?.documents?.map(d => <button key={d.label} className="chip" onClick={() => {
        setBody(null);
        setErr("");
        setSource(d);
      }}>{d.label} · {d.filename}{d.page ? ` · ${d.page}` : ""}</button>)}
      {ctx && <button className="chip" onClick={() => setContext(true)}>{t("context")}</button>}
    </div>
    {source && <Drawer title={`${t("source")} · ${source.filename}`} onClose={() => setSource(null)}><p className="mb-4 text-sm">{t("sourceHelp")}</p>{err ? <p role="alert">{err}</p> : body ? <>{body.note && <p className="mb-3 bg-sun-pale p-3">{body.note}</p>}<p className="font-bold" dir="auto">{body.heading}</p><blockquote className="whitespace-pre-wrap border-s-4 border-pink ps-4 leading-relaxed" dir="auto">{body.text}</blockquote></> : <p role="status">{t("loading")}</p>}</Drawer>}
    {context && <Drawer title={t("context")} onClose={() => setContext(false)}><p className="mb-4 text-sm">{t("contextHelp")}</p><p className="mb-4">{t("history")}: {ctx?.history_messages ?? 0}</p>{ctx?.receipt ? ctx.receipt.map((r, i) => <details key={i} className="sheet mb-3 p-3"><summary className="cursor-pointer font-bold">{t(r.label as DesignKey) || r.label}</summary><pre dir="auto" className="mt-3 whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">{r.text}</pre></details>) : <p>{t("legacy")}</p>}</Drawer>}
  </>;
}
