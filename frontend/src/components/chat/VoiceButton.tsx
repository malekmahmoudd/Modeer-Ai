"use client";

import { useEffect, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/primitives";
import { API_BASE, apiFetch } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";

const MAX_SECONDS = 60;

// Asked once per page load: whether this server can turn speech into text.
let available: Promise<boolean> | null = null;
function voiceAvailable(): Promise<boolean> {
  available ??= apiFetch<{ transcribe: boolean }>("/voice")
    .then((v) => v.transcribe)
    .catch(() => false);
  return available;
}

/** The first recording format this browser supports that the server reads. */
function recordingType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((type) =>
    MediaRecorder.isTypeSupported(type),
  );
}

/**
 * Hold a thought, speak it: records up to a minute, sends it to be written
 * out, and puts the words in the message box to check and edit before sending.
 * Nothing is sent to the agent until the person presses send.
 */
export function VoiceButton({
  disabled,
  onText,
  onError,
  onRecordingChange,
}: {
  disabled?: boolean;
  onText: (text: string) => void;
  onError: (message: string) => void;
  onRecordingChange?: (recording: boolean) => void;
}) {
  const { t, locale } = usePrefs();
  const [shown, setShown] = useState(false);
  const [state, setState] = useState<"idle" | "recording" | "sending">("idle");
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let live = true;
    voiceAvailable().then((ok) => live && setShown(ok && typeof navigator !== "undefined" && !!navigator.mediaDevices));
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => onRecordingChange?.(state === "recording"), [state, onRecordingChange]);

  // Leaving the page mid-recording releases the microphone.
  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
      stream.current?.getTracks().forEach((track) => track.stop());
    },
    [],
  );

  if (!shown) return null;

  async function start() {
    const type = recordingType();
    if (!type) {
      onError(t("voice.unsupported"));
      return;
    }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError(t("voice.denied"));
      return;
    }
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(stream.current, { mimeType: type, audioBitsPerSecond: 32000 });
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      stream.current?.getTracks().forEach((track) => track.stop());
      stream.current = null;
      if (timer.current) clearInterval(timer.current);
      void send(new Blob(chunks, { type: type!.split(";")[0] }));
    };
    recorder.current = rec;
    rec.start();
    setSeconds(0);
    setState("recording");
    timer.current = setInterval(() => {
      setSeconds((s) => {
        if (s + 1 >= MAX_SECONDS) recorder.current?.state === "recording" && recorder.current.stop();
        return s + 1;
      });
    }, 1000);
  }

  function stop() {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }

  async function send(audio: Blob) {
    setState("sending");
    try {
      const form = new FormData();
      const ext = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
      form.append("audio", audio, `voice.${ext}`);
      form.append("language", locale);
      const res = await fetch(`${API_BASE}/voice/transcribe`, { method: "POST", body: form });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : t("voice.failed"));
      const text = String(body?.text ?? "").trim();
      if (text) onText(text);
      else onError(t("voice.empty"));
    } catch (e) {
      onError(e instanceof Error && e.message ? e.message : t("voice.failed"));
    } finally {
      setState("idle");
    }
  }

  const clock = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;

  if (state === "sending") {
    return (
      <span className="grid h-11 w-11 shrink-0 place-items-center" role="status" aria-label={t("voice.transcribing")}>
        <Spinner />
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={state === "recording" ? stop : start}
      disabled={disabled && state !== "recording"}
      aria-pressed={state === "recording"}
      aria-label={state === "recording" ? t("voice.recording", { time: clock }) : t("voice.start")}
      title={state === "recording" ? t("voice.stop") : `${t("voice.start")} — ${t("voice.privacy")}`}
      className={`grid h-11 shrink-0 place-items-center rounded-full transition disabled:opacity-40 ${
        state === "recording"
          ? "min-w-11 gap-1 border-2 border-ink bg-pink px-2.5 text-[12px] font-black text-ink"
          : "w-11 text-ink-soft hover:bg-sun-pale hover:text-ink"
      }`}
    >
      {state === "recording" ? (
        <span className="flex items-center gap-1.5">
          <Icon name="stop" size={14} />
          <span className="tabular-nums" dir="ltr">{clock}</span>
        </span>
      ) : (
        <Icon name="mic" size={20} />
      )}
    </button>
  );
}
