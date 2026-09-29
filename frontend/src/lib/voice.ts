"use client";

import { API_BASE, apiFetch } from "@/lib/api";
import type { Locale } from "@/lib/i18n";

/** What this server can do with voice. Asked once per page load. */
export interface VoiceStatus {
  transcribe: boolean;
  speak: boolean;
}

let status: Promise<VoiceStatus> | null = null;
export function voiceStatus(): Promise<VoiceStatus> {
  status ??= apiFetch<VoiceStatus>("/voice").catch(() => ({ transcribe: false, speak: false }));
  return status;
}

/** The first recording format this browser supports that the server reads. */
export function recordingType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((type) =>
    MediaRecorder.isTypeSupported(type),
  );
}

/** Speech to text. The account's dialect is applied on the server. */
export async function transcribe(audio: Blob, locale: Locale, failed: string): Promise<string> {
  const form = new FormData();
  const ext = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
  form.append("audio", audio, `voice.${ext}`);
  form.append("language", locale);
  const res = await fetch(`${API_BASE}/voice/transcribe`, { method: "POST", body: form });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : failed);
  return String(body?.text ?? "").trim();
}

const ARABIC = /[؀-ۿ]/;

/** Something being read aloud: `done` settles when it ends or is stopped. */
export interface Speaking {
  stop: () => void;
  done: Promise<void>;
}

/** Whether an error only means "cancelled": nothing to report, nothing to fall back to. */
export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function aborted(): DOMException {
  return new DOMException("Reading aloud was stopped.", "AbortError");
}

/** Reads text with the device's own voices: free, and works offline. Null when
 *  the device has no voice for the language. */
export function speakWithDevice(text: string, signal?: AbortSignal): Speaking | null {
  if (signal?.aborted) throw aborted();
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null;
  const synth = window.speechSynthesis;
  const lang = ARABIC.test(text) ? "ar" : "en";
  const voices = synth.getVoices();
  const voice = voices.find((v) => v.lang.toLowerCase().startsWith(lang));
  if (!voice && voices.length > 0) return null;
  synth.cancel();
  let finish = () => {};
  const done = new Promise<void>((resolve) => (finish = resolve));
  // Sentence by sentence: some engines stop after ~15 seconds of one utterance.
  const sentences = text.match(/[^.!?؟\n]+[.!?؟]?/g) ?? [text];
  sentences.forEach((sentence, i) => {
    const u = new SpeechSynthesisUtterance(sentence.trim());
    u.lang = voice?.lang ?? (lang === "ar" ? "ar-EG" : "en-GB");
    if (voice) u.voice = voice;
    if (i === sentences.length - 1) u.onend = finish;
    u.onerror = finish;
    synth.speak(u);
  });
  const stop = () => {
    synth.cancel();
    finish();
  };
  signal?.addEventListener("abort", stop, { once: true });
  return { stop, done };
}

/** Reads text in the server's natural voice (Groq Orpheus). Throws when it is
 *  unavailable, so the caller can fall back to the device; throws an
 *  AbortError when `signal` ends it first, at any stage. */
export async function speakNaturally(text: string, signal?: AbortSignal): Promise<Speaking> {
  if (text.length > 1500) throw new RangeError("Use the device voice for a complete long reply.");
  const res = await fetch(`${API_BASE}/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, language: ARABIC.test(text) ? "ar" : "en" }),
    signal,
  });
  if (!res.ok) throw new Error(String(res.status));
  const blob = await res.blob();
  if (signal?.aborted) throw aborted();
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  let finish = () => {};
  const done = new Promise<void>((resolve) => (finish = resolve));
  let ended = false;
  const end = () => {
    if (ended) return;
    ended = true;
    audio.onended = audio.onerror = null;
    audio.pause();
    audio.removeAttribute("src");
    URL.revokeObjectURL(url);
    finish();
  };
  audio.onended = end;
  audio.onerror = end;
  signal?.addEventListener("abort", end, { once: true });
  try {
    await audio.play();
  } catch (e) {
    end();
    throw signal?.aborted ? aborted() : e;
  }
  if (signal?.aborted) {
    end(); // stopped while playback was starting
    throw aborted();
  }
  return { stop: end, done };
}

// The account's choice (Account › Voice and dialect), set by the app shell.
let preferNatural = true;
export function setPreferNatural(on: boolean) {
  preferNatural = on;
}

/**
 * Natural voice when chosen and available, else the device's voices. Null when
 * no voice can read it. Stopping through `signal`, at any stage, throws an
 * AbortError: nothing plays afterwards and the device voice is not tried.
 */
export async function speak(text: string, signal?: AbortSignal): Promise<Speaking | null> {
  if (signal?.aborted) throw aborted();
  // Keep long replies complete without multiplying provider requests or quota.
  const natural = text.length <= 1500 && preferNatural && (await voiceStatus()).speak;
  if (signal?.aborted) throw aborted();
  if (natural) {
    try {
      return await speakNaturally(text, signal);
    } catch (e) {
      if (signal?.aborted || isAbort(e)) throw aborted();
      /* the day's allowance, the network, or the terms: use the device */
    }
  }
  return speakWithDevice(text, signal);
}
