"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/ui/Icon";

export function ModeerHero() {
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  function open(e: React.FormEvent) {
    e.preventDefault();
    if (pending) return;
    const q = draft.trim();
    setPending(true);
    router.push(q ? `/agents/modeer?q=${encodeURIComponent(q)}` : "/agents/modeer");
  }
  return (
    <section className="sunshine-hero" aria-labelledby="hero-title">
      {/* Artwork is separate; headings and controls remain real HTML. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="sunshine-hero-art" src="/art/sunshine/modeer-hero.webp" alt="Modeer, your illustrated personal assistant, smiling at his desk" fetchPriority="high" />
      <div className="sunshine-hero-copy">
        <h1 id="hero-title" className="display">Meet<br />Modeer</h1>
        <p className="sunshine-subtitle">Your personal AI team.</p>
        <form onSubmit={open} className="sunshine-composer">
          <Icon name="chat" size={21} aria-hidden />
          <label htmlFor="hero-composer" className="sr-only">Message Modeer</label>
          <input id="hero-composer" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Message Modeer…" disabled={pending} />
          <button type="submit" disabled={pending}>
            {pending ? "Opening…" : "Let's talk"}
            {!pending && <Icon name="arrow-right" size={20} aria-hidden />}
          </button>
        </form>
        <p className="hand sunshine-margin-note" aria-hidden="true">Bigger possibilities.<br />Together.</p>
      </div>
    </section>
  );
}
