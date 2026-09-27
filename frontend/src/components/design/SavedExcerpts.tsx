"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch, useApi } from "@/lib/api";
import { useDesignText } from "./text";
import { PocketCard } from "./PocketCard";
export function SavedExcerpts() {
  const {
    data,
    loading,
    error,
    refetch
  } = useApi<{
    message_id: string;
    conversation_id: string;
    agent_id: string;
    title: string;
    excerpts: string[];
  }[]>("/conversations/excerpts");
  const t = useDesignText();
  const [err, setErr] = useState("");
  const [card, setCard] = useState<{
    text: string;
    author: string;
  } | null>(null);
  return <section className="mb-10"><h2 className="display mb-4 text-2xl">{t("notes")}</h2>{loading && <p>{t("loading")}</p>}{(err || error) && <p role="alert">{err || error}</p>}{!loading && !error && !data?.length && <p>{t("empty")}</p>}{data?.map(r => <article key={r.message_id} className="sheet mb-3 p-4"><h3 className="font-bold" dir="auto">{r.title}</h3>{r.excerpts.map((text, i) => <div key={i} className="my-3 border-s-2 border-pink ps-3"><p className="whitespace-pre-wrap" dir="auto">{text}</p><div className="design-actions"><button className="btn" onClick={() => setCard({
            text,
            author: r.title
          })}>{t("pocket")}</button><button className="btn" onClick={async () => {
            try {
              await apiFetch(`/conversations/${r.conversation_id}/messages/${r.message_id}/design`, {
                method: "PATCH",
                body: JSON.stringify({
                  excerpts: r.excerpts.filter((_, j) => j !== i)
                })
              });
              refetch();
            } catch {
              setErr(t("error"));
            }
          }}>{t("remove")}</button></div></div>)}<Link className="underline" href={`/agents/${r.agent_id}?c=${r.conversation_id}&m=${r.message_id}`}>{t("open")}</Link></article>)}{card && <PocketCard {...card} onClose={() => setCard(null)} />}</section>;
}
