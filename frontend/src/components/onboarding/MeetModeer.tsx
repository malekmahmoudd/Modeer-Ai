"use client";

import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { useAgents } from "@/features/agents/useAgents";

export function MeetModeer() {
  const { agents } = useAgents();
  const specialists = agents.filter((a) => !a.is_assistant);

  return (
    <div className="mx-auto max-w-xl anim-fade-up">
      <div className="card relative overflow-hidden p-8 text-center sm:p-10">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 left-1/2 h-56 w-56 -translate-x-1/2 rounded-full blur-3xl"
          style={{ background: "rgba(139,123,255,0.18)" }}
        />
        <span
          className="mx-auto grid h-14 w-14 place-items-center rounded-[16px] text-white"
          style={{
            background: "linear-gradient(150deg, #8b7bff, #5b46d6)",
            boxShadow: "0 16px 40px -16px rgba(139,123,255,0.9)",
          }}
        >
          <Icon name="compass" size={28} />
        </span>
        <h1 className="mt-5 text-[22px] font-semibold tracking-tight text-white">
          Meet Modeer
        </h1>
        <p className="mx-auto mt-2.5 max-w-md text-[14px] leading-relaxed text-content-dim">
          I&apos;m your personal assistant. Tell me a little about yourself — what
          you&apos;re studying or working on, what you&apos;re aiming for — and I&apos;ll
          get your team on the same page.
        </p>
        <Link
          href="/agents/modeer?onboarding=1"
          className="btn btn-accent mx-auto mt-6 w-full sm:w-auto sm:px-6"
        >
          Start with Modeer
          <Icon name="arrow-right" size={15} />
        </Link>
        <p className="mt-3 text-[12px] text-content-faint">
          Takes about a minute. You can edit everything later in Memory.
        </p>
      </div>

      {specialists.length > 0 && (
        <div className="mt-8">
          <p className="mb-3 text-center text-[11px] font-semibold uppercase tracking-[0.14em] text-content-faint">
            Then your team is ready
          </p>
          <div className="flex flex-wrap justify-center gap-2 opacity-70">
            {specialists.map((a) => (
              <span key={a.id} className="tag">
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: a.accent }}
                />
                {a.icon} {a.name.replace(" Agent", "")}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
