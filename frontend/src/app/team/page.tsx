"use client";

import { AgentGrid } from "@/components/AgentGrid";
import { SectionHeading } from "@/components/ui/primitives";

export default function TeamPage() {
  return (
    <div className="mx-auto max-w-5xl animate-fade-up">
      <div className="mb-8">
        <p className="text-sm text-white/40">AI Team</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-white">
          Choose who you want to talk to
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-white/50">
          Nine specialists and Modeer, your personal assistant. They share what your
          team knows about you, but each keeps its own conversation and its own notes.
        </p>
      </div>

      <SectionHeading title="Personal assistant" />
      <AgentGrid assistantsOnly />

      <div className="mt-10">
        <SectionHeading title="Specialists" />
        <AgentGrid specialistsOnly />
      </div>
    </div>
  );
}
