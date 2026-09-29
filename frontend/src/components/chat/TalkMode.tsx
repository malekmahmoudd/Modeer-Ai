"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { plainText } from "@/components/chat/MessageActions";
import { usePrefs } from "@/lib/i18n";
import { isAbort, recordingType, speak, transcribe } from "@/lib/voice";

type Phase = "listening" | "hearing" | "transcribing" | "waiting" | "speaking" | "paused";

/** Longest single turn, and how long to wait for someone to start talking. */
const MAX_TURN_MS = 45_000;
const IDLE_MS = 20_000;
/** A pause this long after speech ends the turn. */
const SILENCE_MS = 1_300;

/**
 * Hands-free conversation: listens, sends what was said when the person
 * pauses, reads the reply aloud, and listens again. The microphone is off
 * while a reply is read, so the reply is never heard as the next message.
 * Twenty seconds of silence pauses it; nothing is recorded in the meantime.
 *
 * Every step that waits (the microphone permission, the recording, writing it
 * out, the reply's voice) belongs to one turn in one `context` (the chat and
 * its privacy mode). When the context changes, the turn is cancelled: the
 * microphone is released, anything still arriving is thrown away, and talk
 * mode closes. What was said is never sent to a different chat.
 */
export function TalkMode({
  streaming,
  reply,
  context,
  onHeard,
  onExit,
}: {
  streaming: boolean;
  /** The latest finished reply: read aloud when it is new. */
  reply: { id: string; content: string } | null;
  /** Names the chat and privacy mode speech is for. */
  context: string;
  onHeard: (text: string) => void;
  onExit: () => void;
}) {
  const { t, locale } = usePrefs();
  const [phase, setPhase] = useState<Phase>("listening");
  const [note, setNote] = useState("");
  const stream = useRef<MediaStream | null>(null);
  const audio = useRef<AudioContext | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const loop = useRef<ReturnType<typeof setInterval> | null>(null);
  const reading = useRef<AbortController | null>(null);
  const answered = useRef<string | null>(reply?.id ?? null);
  const live = useRef(true);
  // Which turn is current: a step from an older turn finds a different number
  // and stops.
  const turn = useRef(0);
  const openedIn = useRef(context);
  const contextNow = useRef(context);
  const heard = useRef(onHeard);
  const exit = useRef(onExit);
  useLayoutEffect(() => {
    contextNow.current = context;
    heard.current = onHeard;
    exit.current = onExit;
  });
  // listen() starts the next turn from inside the current one.
  const again = useRef<() => void>(() => {});

  const release = useCallback(() => {
    if (loop.current) clearInterval(loop.current);
    loop.current = null;
    if (recorder.current) {
      recorder.current.onstop = null;
      recorder.current.ondataavailable = null;
      if (recorder.current.state !== "inactive") recorder.current.stop();
    }
    recorder.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    void audio.current?.close().catch(() => undefined);
    audio.current = null;
  }, []);

  /** Ends the current turn: nothing from it may send, speak or listen again. */
  const cancel = useCallback(() => {
    turn.current += 1;
    reading.current?.abort();
    reading.current = null;
    release();
  }, [release]);

  const listen = useCallback(async () => {
    cancel();
    const mine = turn.current;
    const current = () => live.current && turn.current === mine && contextNow.current === openedIn.current;
    setNote("");
    const type = recordingType();
    if (!type || !navigator.mediaDevices) {
      setNote(t("voice.unsupported"));
      setPhase("paused");
      return;
    }
    let mic: MediaStream;
    try {
      mic = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch {
      if (current()) {
        setNote(t("voice.denied"));
        setPhase("paused");
      }
      return;
    }
    if (!current()) {
      // The permission arrived after the turn ended: let go of it at once.
      mic.getTracks().forEach((track) => track.stop());
      return;
    }
    stream.current = mic;
    setPhase("listening");

    // Loudness, ten times a second, against the room's own noise level.
    const room = new AudioContext();
    audio.current = room;
    const analyser = room.createAnalyser();
    analyser.fftSize = 1024;
    room.createMediaStreamSource(mic).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);
    const loudness = () => {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (const s of samples) sum += s * s;
      return Math.sqrt(sum / samples.length);
    };

    const chunks: Blob[] = [];
    const rec = new MediaRecorder(mic, { mimeType: type, audioBitsPerSecond: 32000 });
    recorder.current = rec;
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = async () => {
      recorder.current = null; // already stopped; release() must not stop it again
      release();
      if (!current()) return;
      setPhase("transcribing");
      try {
        const text = await transcribe(new Blob(chunks, { type: type.split(";")[0] }), locale, t("voice.failed"));
        if (!current()) return; // the chat or privacy mode changed meanwhile
        if (text) {
          setPhase("waiting");
          heard.current(text);
        } else {
          again.current();
        }
      } catch (e) {
        if (!current()) return;
        setNote(e instanceof Error ? e.message : t("voice.failed"));
        setPhase("paused");
      }
    };
    rec.start();

    const started = Date.now();
    let floor = 0;
    let calibrating = 5;
    let loudSince = 0;
    let spoke = false;
    let quietSince = 0;
    loop.current = setInterval(() => {
      if (!current()) return release();
      const level = loudness();
      const now = Date.now();
      if (calibrating > 0) {
        floor = Math.max(floor, level);
        calibrating -= 1;
        return;
      }
      const threshold = Math.max(0.015, floor * 2.5);
      if (level > threshold) {
        loudSince ||= now;
        quietSince = 0;
        if (!spoke && now - loudSince > 200) {
          spoke = true;
          setPhase("hearing");
        }
      } else {
        loudSince = 0;
        quietSince ||= now;
      }
      const done = spoke && quietSince && now - quietSince > SILENCE_MS;
      if (done || now - started > MAX_TURN_MS) {
        if (loop.current) clearInterval(loop.current);
        loop.current = null;
        rec.stop();
      } else if (!spoke && now - started > IDLE_MS) {
        release();
        setNote(t("talk.idle"));
        setPhase("paused");
      }
    }, 100);
  }, [cancel, locale, release, t]);
  useEffect(() => {
    again.current = () => void listen();
  }, [listen]);

  // Start listening when talk mode opens; let go of everything when it closes.
  useEffect(() => {
    live.current = true;
    void listen();
    return () => {
      live.current = false;
      cancel();
    };
    // Only on open and close.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Another chat, another teammate or incognito: this conversation is over.
  useEffect(() => {
    if (context === openedIn.current) return;
    cancel();
    exit.current();
  }, [context, cancel]);

  // A new reply has finished: read it, then listen again.
  const phaseNow = useRef(phase);
  useEffect(() => {
    phaseNow.current = phase;
  }, [phase]);
  useEffect(() => {
    if (streaming || !reply || reply.id === answered.current || phaseNow.current !== "waiting") return;
    answered.current = reply.id;
    const mine = turn.current;
    const controller = new AbortController();
    reading.current = controller;
    setPhase("speaking");
    void (async () => {
      try {
        const voice = await speak(plainText(reply.content), controller.signal);
        if (voice) await voice.done;
        else setNote(t("msg.noVoice"));
      } catch (e) {
        if (!isAbort(e)) setNote(t("msg.noVoice"));
      }
      if (reading.current === controller) reading.current = null;
      // Skip ends the reading, not the conversation; a cancelled turn ends both.
      if (live.current && turn.current === mine) void listen();
    })();
  }, [streaming, reply, listen, t]);

  // The reply failed (no new reply once streaming stops): listen again.
  useEffect(() => {
    if (phase !== "waiting" || streaming) return;
    const timer = setTimeout(() => {
      if (live.current && (!reply || reply.id === answered.current)) void listen();
    }, 1500);
    return () => clearTimeout(timer);
  }, [phase, streaming, reply, listen]);

  const label = t(`talk.${phase}`);
  return (
    <div role="region" aria-label={t("talk.title")} className="mb-2 flex flex-wrap items-center gap-3 border-2 border-ink bg-sun-pale px-3 py-2">
      <span className={`grid h-9 w-9 place-items-center rounded-full border-2 border-ink ${phase === "hearing" ? "bg-pink" : "bg-paper-hi"}`} aria-hidden>
        <Icon name={phase === "speaking" ? "speaker" : "mic"} size={18} />
      </span>
      <p role="status" className="min-w-0 flex-1 text-[14px] font-bold">
        {label}
        {note && <span className="block text-[12.5px] font-semibold text-ink-soft">{note}</span>}
      </p>
      {phase === "speaking" && (
        <button type="button" className="btn" onClick={() => reading.current?.abort()}>{t("talk.skip")}</button>
      )}
      {phase === "paused" && (
        <button type="button" className="btn btn-sun" onClick={() => void listen()}>{t("talk.resume")}</button>
      )}
      <button type="button" className="btn" onClick={onExit}>{t("talk.end")}</button>
    </div>
  );
}
