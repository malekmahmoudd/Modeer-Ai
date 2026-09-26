"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { usePrefs } from "@/lib/i18n";

export function ModeerHero({ onboarding = false }: { onboarding?: boolean }) {
  const router = useRouter();
  const { t, dataSaver } = usePrefs();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  function open(e: React.FormEvent) {
    e.preventDefault();
    if (pending) return;
    const q = draft.trim();
    setPending(true);
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (onboarding) params.set("onboarding", "1");
    const query = params.toString();
    router.push(`/agents/modeer${query ? `?${query}` : ""}`);
  }
  return (
    <section className="sunshine-hero" aria-labelledby="hero-title">
      {/* Artwork is separate; headings and controls remain real HTML. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {!dataSaver && <img className="sunshine-hero-art" src="/art/sunshine/modeer-hero.webp" alt={t("hero.alt")} fetchPriority="high" />}
      <div className="sunshine-hero-copy">
        <h1 id="hero-title" className="display">{t("hero.meet")}<br />{t("common.leo")}</h1>
        <p className="sunshine-subtitle">{t("hero.subtitle")}</p>
        <form onSubmit={open} className="sunshine-composer">
          <Icon name="chat" size={21} aria-hidden />
          <label htmlFor="hero-composer" className="sr-only">{t("hero.messageLeo")}</label>
          <input id="hero-composer" dir="auto" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t("hero.placeholder")} disabled={pending} />
          <button type="submit" disabled={pending}>
            {pending ? t("hero.opening") : t("hero.cta")}
            {!pending && <Icon name="arrow-right" size={20} aria-hidden />}
          </button>
        </form>
        <p className="hand sunshine-margin-note" aria-hidden="true">{t("hero.note1")}<br />{t("hero.note2")}</p>
      </div>
    </section>
  );
}
