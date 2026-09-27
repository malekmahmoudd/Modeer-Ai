"use client";

import { useState } from "react";
import { Drawer } from "./Drawer";
import { useDesignText } from "./text";
import { escapeHTML } from "@/lib/design";
import { usePrefs } from "@/lib/i18n";
export function PocketCard({
  text,
  author,
  onClose
}: {
  text: string;
  author: string;
  onClose: () => void;
}) {
  const t = useDesignText();
  const {
    locale
  } = usePrefs();
  const [kind, setKind] = useState<"interview" | "packing" | "study">("study");
  const [title, setTitle] = useState<string>(t("study"));
  const [body, setBody] = useState(text);
  const lines = body.split("\n").map(line => line.replace(/^\s*[-*•]\s+/, "").trim()).filter(Boolean);
  function download() {
    const content = kind === "study"
      ? `<pre dir="auto">${escapeHTML(body)}</pre>`
      : `<ol class="${kind}">${lines.map(line => `<li dir="auto">${escapeHTML(line)}</li>`).join("")}</ol>`;
    const color = kind === "packing" ? "#ff438a" : kind === "study" ? "#202d3b" : "#ffda45";
    const html = `<!doctype html><html lang="${locale}" dir="${locale === "ar" ? "rtl" : "ltr"}"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${escapeHTML(title)}</title><style>body{font:18px/1.7 system-ui,sans-serif;background:#fff7df;color:#151714;margin:24px}article{max-width:650px;margin:auto;padding:30px;border:2px solid #151714;border-top:14px solid ${color};background:#fffcf2;box-shadow:5px 5px #151714}h1{line-height:1.2}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}ol{padding-inline-start:1.5em}li{padding:8px 4px;border-bottom:1px solid #15171433;break-inside:avoid}.packing{list-style:none;padding:0}.packing li::before{content:"□ ";font-size:22px}.interview li::marker{font-weight:bold}footer{font-size:12px;border-top:1px solid;padding-top:12px}@media print{body{margin:0;background:white}article{box-shadow:none;max-width:none;break-inside:auto}}</style><article><p>FAREEQ · ${escapeHTML(t(kind))}</p><h1 dir="auto">${escapeHTML(title)}</h1>${content}<footer>${escapeHTML(author)} · ${escapeHTML(new Date().toLocaleDateString(locale))}</footer></article></html>`;
    const url = URL.createObjectURL(new Blob([html], {
      type: "text/html;charset=utf-8"
    }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "fareeq-pocket-card.html";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <Drawer title={t("pocket")} onClose={onClose}>
    <p className="mb-4 text-sm">{t("cardHelp")}</p>
    <label className="mb-3 block">{t("cardType")}<select className="field mt-1" value={kind} onChange={e => {
        const k = e.target.value as typeof kind;
        setKind(k);
        setTitle(t(k));
      }}>{(["interview", "packing", "study"] as const).map(k => <option key={k} value={k}>{t(k)}</option>)}</select></label>
    <label className="mb-3 block">{t("cardTitle")}<input dir="auto" className="field mt-1" maxLength={120} value={title} onChange={e => setTitle(e.target.value)} /></label>
    <label className="mb-5 block">{t("excerpt")}<textarea dir="auto" className="field mt-1 min-h-40" maxLength={20000} value={body} onChange={e => setBody(e.target.value)} /></label>
    <article className={`pocket-preview pocket-${kind}`}><p className="eyebrow">FAREEQ · {t(kind)}</p><h3 className="my-3 text-2xl font-black" dir="auto">{title}</h3>{kind === "study" ? <div dir="auto">{body}</div> : <ol className={kind === "packing" ? "list-none" : "list-decimal ps-5"}>{lines.map((line, i) => <li key={i} dir="auto" className="border-b border-ink/20 py-2">{kind === "packing" && <span aria-hidden="true">□ </span>}{line}</li>)}</ol>}<footer className="mt-4 border-t border-ink pt-3 text-xs">{author}</footer></article>
    <button className="btn btn-pink mt-5" disabled={!body.trim() || !title.trim()} onClick={download}>{t("download")}</button>
  </Drawer>;
}
