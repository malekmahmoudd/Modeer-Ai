"use client";

import Link from "next/link";
import { useState } from "react";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { Icon } from "@/components/ui/Icon";
import { ErrorNote, ThinkingDots } from "@/components/ui/primitives";
import { useAgents } from "@/features/agents/useAgents";
import { apiFetch } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
import { renderMarkdown } from "@/lib/markdown";
import type { TeamAnswer } from "@/types";

const MAX_TEAM = 3;

/**
 * One question to up to three specialists at once; Leo brings their answers
 * together. Every answer is kept in that specialist's history, so any of them
 * can be carried on in a normal chat.
 */
export function AskTeam() {
  const { t } = usePrefs();
  const { agents, byId } = useAgents();
  const agentName = useAgentName();
  const specialists = agents.filter((a) => !a.is_assistant);
  const [question, setQuestion] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState<TeamAnswer | null>(null);

  function toggle(id: string) {
    setNote("");
    if (picked.includes(id)) setPicked(picked.filter((p) => p !== id));
    else if (picked.length >= MAX_TEAM) setNote(t("team.limit"));
    else setPicked([...picked, id]);
  }

  async function ask(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    if (!picked.length) {
      setNote(t("team.pickOne"));
      return;
    }
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(
        await apiFetch<TeamAnswer>("/team/ask", {
          method: "POST",
          body: JSON.stringify({ question: question.trim(), agent_ids: picked }),
        }),
      );
    } catch (ex) {
      setError(t("team.error", { error: ex instanceof Error ? ex.message : t("common.failed") }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mb-10 border-2 border-ink bg-paper-hi p-5 shadow-pop-xs" aria-labelledby="ask-team-title">
      <h2 id="ask-team-title" className="display text-[clamp(22px,3vw,28px)] text-ink">
        {t("team.ask")}
      </h2>
      <p className="mt-2 max-w-[60ch] text-[14px] text-ink-soft">{t("team.askHelp")}</p>

      <form onSubmit={ask} className="mt-4">
        <label htmlFor="team-question" className="mb-1.5 block font-bold">
          {t("team.question")}
        </label>
        <textarea
          id="team-question"
          dir="auto"
          rows={2}
          maxLength={4000}
          className="field min-h-[72px]"
          placeholder={t("team.questionPlaceholder")}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
        />
        <fieldset className="mt-3">
          <legend className="mb-2 font-bold">{t("team.pick")}</legend>
          <ul className="flex flex-wrap gap-2">
            {specialists.map((a) => {
              const on = picked.includes(a.id);
              return (
                <li key={a.id}>
                  <button
                    type="button"
                    aria-pressed={on}
                    disabled={busy}
                    onClick={() => toggle(a.id)}
                    className={`flex items-center gap-2 border-2 border-ink py-1 pe-3 ps-1 text-[13px] font-bold transition ${
                      on ? "bg-pink text-ink shadow-pop-xs" : "bg-paper-hi text-ink hover:bg-sun-pale"
                    }`}
                  >
                    <AgentBadge slug={a.id} size={28} />
                    {agentName(a)}
                  </button>
                </li>
              );
            })}
          </ul>
          {note && (
            <p role="status" className="mt-2 text-[13px] font-semibold text-pink-deep">
              {note}
            </p>
          )}
        </fieldset>
        <button type="submit" disabled={busy || !question.trim()} className="btn btn-pink mt-4">
          <Icon name="team" size={17} /> {t("team.askButton")}
        </button>
      </form>

      {busy && (
        <p className="mt-5 flex items-center gap-2 text-[14px] font-semibold text-ink-soft" role="status">
          <ThinkingDots /> {t("team.asking")}
        </p>
      )}
      {error && (
        <div className="mt-4">
          <ErrorNote message={error} />
        </div>
      )}

      {answer && (
        <div className="anim-in mt-6">
          <div className="border-2 border-ink bg-sun-pale p-4">
            <p className="mb-2 flex items-center gap-2 text-[12px] font-black uppercase tracking-wide text-ink">
              <AgentBadge slug="modeer" size={28} /> {t("team.combined")}
            </p>
            <div className="prose-ink">{renderMarkdown(answer.synthesis)}</div>
            {answer.conversation_id && (
              <Link
                href={`/agents/modeer?c=${answer.conversation_id}`}
                className="mt-2 inline-block text-[13px] font-bold underline decoration-pink decoration-2 underline-offset-4"
              >
                {t("team.openLeo")}
              </Link>
            )}
          </div>
          <h3 className="eyebrow mb-2 mt-5">{t("team.answers")}</h3>
          <ul className="flex flex-col gap-2.5">
            {answer.takes.map((take) => (
              <li key={take.agent_id}>
                <details className="border-2 border-ink bg-paper-hi">
                  <summary className="flex cursor-pointer items-center gap-2 px-3 py-2.5 font-bold text-ink">
                    <AgentBadge slug={take.agent_id} size={28} />
                    {agentName(byId(take.agent_id), take.name)}
                  </summary>
                  <div className="border-t-2 border-ink px-4 py-3">
                    <div className="prose-ink">{renderMarkdown(take.answer)}</div>
                    {take.conversation_id && (
                      <Link
                        href={`/agents/${take.agent_id}?c=${take.conversation_id}`}
                        className="mt-2 inline-flex items-center gap-1.5 text-[13px] font-bold underline decoration-pink decoration-2 underline-offset-4"
                      >
                        {t("team.continueWith", { name: agentName(byId(take.agent_id), take.name) })}
                        <Icon name="arrow-right" size={14} />
                      </Link>
                    )}
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
