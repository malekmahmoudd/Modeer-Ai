"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AgentPortrait } from "@/components/art/AgentPortrait";
import { HeroDiagonals, Scribble } from "@/components/art/Ink";
import { Icon } from "@/components/ui/Icon";

/**
 * "Meet Modeer" — heavy display type and a real composer on the left,
 * Modeer's illustrated portrait dominating the right, over broad diagonal
 * cream / yellow / pink fields.
 *
 * The composer submits into the existing Modeer conversation flow: the
 * workspace picks up `?q=` and sends it as the first streamed message.
 */
export function ModeerHero() {
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);

  // Empty field opens Modeer; text is sent as the first streamed message.
  function open(e: React.FormEvent) {
    e.preventDefault();
    if (pending) return;
    const q = draft.trim();
    setPending(true);
    router.push(q ? `/agents/modeer?q=${encodeURIComponent(q)}` : "/agents/modeer");
  }

  return (
    <section className="relative -mx-4 overflow-hidden border-b-2 border-ink sm:-mx-7">
      <HeroDiagonals />

      <div className="relative mx-auto grid w-full max-w-page grid-cols-1 items-end gap-x-6 px-4 pt-8 sm:px-7 md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] md:pt-10">
        {/* ---------- left: headline + composer ---------- */}
        <div className="pb-6 md:pb-12">
          <h1 className="display text-[clamp(48px,10.5vw,92px)] text-ink">
            Meet
            <br />
            Modeer
          </h1>

          <p className="mt-4 text-[clamp(17px,2.2vw,23px)] font-semibold text-ink">
            Your <span className="font-normal">personal</span> AI team.
          </p>

          {/* real composer */}
          <form
            onSubmit={open}
            className="mt-6 flex w-full max-w-[430px] items-center gap-2 rounded-full border-2 border-ink bg-paper-hi p-1.5 pl-4 shadow-pop-sm"
          >
            <Icon name="chat" size={19} className="shrink-0 text-ink-soft" aria-hidden />
            <label htmlFor="hero-composer" className="sr-only">
              Message Modeer
            </label>
            <input
              id="hero-composer"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Message Modeer…"
              disabled={pending}
              className="min-w-0 flex-1 bg-transparent py-2 text-[15px] text-ink outline-none placeholder:text-ink-faint disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={pending}
              className="btn btn-pink !min-h-[44px] shrink-0 !px-5 !text-[14px]"
            >
              {pending ? "Opening…" : "Let's talk"}
              {!pending && <Icon name="arrow-right" size={16} />}
            </button>
          </form>

          <Scribble className="mt-7 block max-w-[230px]" underline>
            Bigger possibilities
            <br />
            together.
          </Scribble>
        </div>

        {/* ---------- right: portrait ---------- */}
        <div className="relative">
          <Scribble
            className="absolute -left-2 top-6 z-10 hidden max-w-[130px] xl:block"
            tone="ink"
          >
            Same brighter
            <br />
            you.
          </Scribble>

          <div className="relative mx-auto h-[262px] w-full max-w-[330px] sm:h-[330px] sm:max-w-[400px] md:h-[420px] md:max-w-[460px] lg:h-[500px] lg:max-w-[520px]">
            <AgentPortrait
              slug="modeer"
              framing="hero"
              transparent
              fit="contain"
              className="absolute inset-x-0 bottom-0 h-full w-full"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
