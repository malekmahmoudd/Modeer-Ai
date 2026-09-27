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

/** Reads text with the device's own voices: free, and works offline. Null when
 *  the device has no voice for the language. */
export function speakWithDevice(text: string): Speaking | null {
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
  return {
    stop: () => {
      synth.cancel();
      finish();
    },
    done,
  };
}

/** Reads text in the server's natural voice (Groq Orpheus). Throws when it is
 *  unavailable, so the caller can fall back to the device. */
export async function speakNaturally(text: string, signal?: AbortSignal): Promise<Speaking> {
  const res = await fetch(`${API_BASE}/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text.slice(0, 1500), language: ARABIC.test(text) ? "ar" : "en" }),
    signal,
  });
  if (!res.ok) throw new Error(String(res.status));
  const url = URL.createObjectURL(await res.blob());
  const audio = new Audio(url);
  let finish = () => {};
  const done = new Promise<void>((resolve) => (finish = resolve));
  const end = () => {
    URL.revokeObjectURL(url);
    finish();
  };
  audio.onended = end;
  audio.onerror = end;
  await audio.play();
  return {
    stop: () => {
      audio.pause();
      end();
    },
    done,
  };
}

// The account's choice (Account > Voice), set by the app shell when it loads.
let preferNatural = true;
export function setPreferNatural(on: boolean) {
  preferNatural = on;
}

/** Natural voice when chosen and available, else the device's voices. */
export async function speak(text: string): Promise<Speaking | null> {
  if (preferNatural && (await voiceStatus()).speak) {
    try {
      return await speakNaturally(text);
    } catch {
      /* the day's allowance, the network, or the terms: use the device */
    }
  }
  return speakWithDevice(text);
}
