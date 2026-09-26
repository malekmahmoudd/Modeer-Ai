"use client";

import Link from "next/link";
import { Brand } from "@/components/Brand";
import { useApi } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";
import { renderMarkdown } from "@/lib/markdown";

export default function PrivacyPage() {
  const {data, error, loading, refetch} = useApi<{content:string}>("/legal/privacy");
  const { t } = usePrefs();
  return <div className="min-h-dvh bg-paper px-4 py-7 sm:px-7">
    <div className="mx-auto max-w-3xl">
      <header className="flex items-center justify-between gap-4 border-b-2 border-ink pb-5"><Brand size="sm"/><Link href="/login" className="btn btn-sun me-14">{t("common.signIn")}</Link></header>
      <article className="my-7 border-2 border-ink bg-paper-hi p-5 sm:p-8 shadow-pop-xs break-words">
        {loading && <p role="status">{t("privacy.loading")}</p>}
        {error && <div role="alert"><p>{error}</p><button className="btn mt-4" onClick={refetch}>{t("common.tryAgain")}</button></div>}
        {data && <><h1 className="font-display text-3xl mb-5">{data.content.split("\n")[0].replace(/^#\s+/, "")}</h1>{renderMarkdown(data.content.split("\n").slice(1).join("\n"))}</>}
      </article>
      <Link href="/account" className="inline-block py-3 underline">{t("privacy.manage")}</Link>
    </div>
  </div>;
}
