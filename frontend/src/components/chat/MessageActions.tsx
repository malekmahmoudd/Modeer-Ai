"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AgentBadge } from "@/components/art/AgentPortrait";
import { Icon } from "@/components/ui/Icon";
import { useAgents } from "@/features/agents/useAgents";
import { usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";

const ARABIC = /[؀-ۿ]/;
/** Longest excerpt carried to a teammate; the rest is still in this chat. */
const PASS_LIMIT = 1500;
export const HANDOFF_KEY = "fareeq.handoff";

/** Markdown to plain sentences, for reading aloud and plain copying. */
export function plainText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\|?[-: |]+\|?\s*$/gm, "")
    .replace(/\|/g, " ")
    .replace(/(\*\*|__|\*|_|~~)/g, "")
    .replace(/^>\s?/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function Action({
  icon,
  label,
  onClick,
  pressed,
  text,
}: {
  icon: Parameters<typeof Icon>[0]["name"];
  label: string;
  onClick: () => void;
  pressed?: boolean;
  text?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className={`inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-bold transition hover:bg-sun-pale ${
        pressed ? "bg-sun-pale text-ink" : "text-ink-soft"
      }`}
    >
      <Icon name={icon} size={15} />
      {text && <span>{text}</span>}
    </button>
  );
}

/** Reads a reply aloud with the device's own voices: free, and offline. */
function ListenButton({ text }: { text: string }) {
  const { t } = usePrefs();
  const [speaking, setSpeaking] = useState(false);
  const [note, setNote] = useState("");
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => () => {
    if (speaking) window.speechSynthesis.cancel();
  }, [speaking]);

  if (!supported) return null;

  function speak() {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    const plain = plainText(text);
    const lang = ARABIC.test(plain) ? "ar" : "en";
    const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang));
    if (!voice && synth.getVoices().length > 0) {
      setNote(t("msg.noVoice"));
      return;
    }
    synth.cancel();
    // Sentence by sentence: some engines stop after ~15 seconds of one utterance.
    const sentences = plain.match(/[^.!?؟\n]+[.!?؟]?/g) ?? [plain];
    sentences.forEach((sentence, i) => {
      const u = new SpeechSynthesisUtterance(sentence.trim());
      u.lang = voice?.lang ?? (lang === "ar" ? "ar-EG" : "en-GB");
      if (voice) u.voice = voice;
      if (i === sentences.length - 1) u.onend = () => setSpeaking(false);
      u.onerror = () => setSpeaking(false);
      synth.speak(u);
    });
    setSpeaking(true);
  }

  return (
    <>
      <Action
        icon={speaking ? "stop" : "speaker"}
        label={speaking ? t("msg.stopListening") : t("msg.listen")}
        pressed={speaking}
        onClick={speak}
      />
      {note && (
        <span role="status" className="text-[11.5px] font-semibold text-ink-faint">
          {note}
        </span>
      )}
    </>
  );
}

/** "Ask Harvey about this": opens a teammate with the reply quoted as a draft. */
function PassMenu({ fromAgent, text }: { fromAgent: string; text: string }) {
  const router = useRouter();
  const { t } = usePrefs();
  const { agents, byId } = useAgents();
  const agentName = useAgentName();
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menu.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  function pass(to: string) {
    let excerpt = plainText(text);
    if (excerpt.length > PASS_LIMIT) excerpt = `${excerpt.slice(0, PASS_LIMIT).trimEnd()}…`;
    const quoted = excerpt
      .split("\n")
      .map((line) => `> ${line}`)
      .join("\n");
    const draft = t("msg.passDraft", { name: agentName(byId(fromAgent), fromAgent), excerpt: quoted });
    // Handed over in this tab's storage, not the address bar: the reply may be
    // personal, and a URL ends up in history.
    try {
      window.sessionStorage.setItem(HANDOFF_KEY, draft);
      router.push(`/agents/${to}?handoff=1`);
    } catch {
      router.push(`/agents/${to}?draft=${encodeURIComponent(draft.slice(0, 1800))}`);
    }
  }

  return (
    <div ref={menu} className="relative">
      <Action icon="forward" label={t("msg.pass")} text={t("msg.pass")} onClick={() => setOpen(!open)} pressed={open} />
      {open && (
        <ul
          role="menu"
          aria-label={t("msg.pass")}
          className="absolute bottom-full start-0 z-30 mb-1 max-h-72 w-60 overflow-y-auto border-2 border-ink bg-paper-hi p-1 shadow-pop-sm"
        >
          {agents
            .filter((a) => a.id !== fromAgent)
            .map((a) => (
              <li key={a.id} role="none">
                <button
                  role="menuitem"
                  onClick={() => pass(a.id)}
                  className="flex w-full items-center gap-2 px-2 py-1.5 text-start text-[13px] font-bold text-ink hover:bg-sun-pale"
                >
                  <AgentBadge slug={a.id} size={26} />
                  {t("msg.passTo", { name: agentName(a) })}
                </button>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}

/** The row under a finished reply. */
export function ReplyActions({
  agentId,
  text,
  saved,
  onToggleSave,
  onRegenerate,
}: {
  agentId: string;
  text: string;
  saved: boolean;
  /** Absent while the reply has no server id yet, or in an incognito chat. */
  onToggleSave?: () => void;
  /** Only on the latest reply. */
  onRegenerate?: () => void;
}) {
  const { t } = usePrefs();
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-0.5" role="group" aria-label={t("msg.actions")}>
      <Action icon={copied ? "check" : "copy"} label={copied ? t("msg.copied") : t("msg.copy")} onClick={copy} />
      {onToggleSave && (
        <Action
          icon="bookmark"
          label={saved ? t("msg.unsaveLabel") : t("msg.saveLabel")}
          text={saved ? t("msg.saved") : undefined}
          pressed={saved}
          onClick={onToggleSave}
        />
      )}
      <ListenButton text={text} />
      <PassMenu fromAgent={agentId} text={text} />
      {onRegenerate && <Action icon="refresh" label={t("msg.regenerate")} onClick={onRegenerate} />}
      <span className="sr-only" role="status">
        {copied ? t("msg.copied") : ""}
      </span>
    </div>
  );
}
