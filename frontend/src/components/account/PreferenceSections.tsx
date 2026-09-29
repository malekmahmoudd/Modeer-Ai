"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { forgetHiddenAgents, useAgents } from "@/features/agents/useAgents";
import { applyA11y, TEXT_SCALES } from "@/lib/a11y";
import { apiFetch } from "@/lib/api";
import type { DesignPreferences } from "@/lib/design";
import { intlTag, usePrefs } from "@/lib/i18n";
import { useAgentName } from "@/lib/i18n/agents";
import { disablePush, enablePush, pushOn, pushSupported } from "@/lib/push";
import { setPreferNatural, voiceStatus } from "@/lib/voice";
import type { Dialect, UserProfile } from "@/types";

interface Props {
  me: UserProfile | null;
  setMe: (me: UserProfile) => void;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
}

const noSubscribe = () => () => {};
const SECTION = "border-2 border-ink bg-paper-hi p-5 shadow-pop-xs";
const DIALECTS: (Dialect | "auto")[] = ["auto", "msa", "egyptian", "gulf", "levantine"];

/** Saves interface choices on the account; shows them at once, undoes on failure. */
function usePreferenceSaver({ me, setMe, onNotice, onError }: Props) {
  const { t } = usePrefs();
  return async (patch: DesignPreferences) => {
    if (!me) return;
    const before = me;
    setMe({ ...me, ui_preferences: { ...me.ui_preferences, ...patch } });
    try {
      setMe(await apiFetch<UserProfile>("/users/me", { method: "PATCH", body: JSON.stringify({ ui_preferences: patch }) }));
      if (patch.hidden_agents) forgetHiddenAgents();
      onNotice(t("prefs.saved"));
    } catch (e) {
      setMe(before);
      onError(e instanceof Error ? e.message : t("common.failed"));
    }
  };
}

/** A daily notification with what is due, on the devices the person chooses. */
export function RemindersSection(props: Props) {
  const { t, locale } = usePrefs();
  const save = usePreferenceSaver(props);
  const prefs = props.me?.ui_preferences;
  const [on, setOn] = useState<boolean | null>(null);
  const [leftover, setLeftover] = useState(false);
  const [busy, setBusy] = useState(false);
  // False while the server renders and during hydration; the browser's answer after.
  const supported = useSyncExternalStore(noSubscribe, pushSupported, () => false);

  useEffect(() => {
    if (!supported) return;
    let live = true;
    pushOn()
      .then((state) => {
        if (!live) return;
        setOn(state.on);
        setLeftover(state.leftover);
      })
      .catch(() => live && setOn(false));
    return () => {
      live = false;
    };
  }, [supported]);

  async function toggle(next: boolean) {
    setBusy(true);
    try {
      if (next) {
        const result = await enablePush();
        if (result === "on") {
          setOn(true);
          setLeftover(false);
          props.onNotice(t("prefs.remindersEnabled"));
        } else {
          props.onError(
            t(result === "denied" ? "prefs.remindersDenied" : result === "unavailable" ? "prefs.remindersUnavailable" : "prefs.remindersUnsupported"),
          );
        }
      } else {
        await disablePush();
        setOn(false);
        props.onNotice(t("prefs.remindersDisabled"));
      }
    } catch (e) {
      props.onError(e instanceof Error ? e.message : t("common.failed"));
    } finally {
      setBusy(false);
    }
  }

  const hour = prefs?.push_hour ?? 8;
  const clock = (h: number) =>
    new Intl.DateTimeFormat(locale === "ar" ? "ar-EG" : undefined, { hour: "numeric" }).format(new Date(2000, 0, 1, h));

  return (
    <section className={SECTION}>
      <h2 className="display text-2xl">{t("prefs.reminders")}</h2>
      <p className="my-3 text-ink-soft">{t("prefs.remindersHelp")}</p>
      {leftover && !on && <p role="status" className="mb-3 border-2 border-ink bg-sun-pale p-3 font-semibold">{t("prefs.remindersAgain")}</p>}
      {!supported ? (
        <p className="font-semibold">{t("prefs.remindersUnsupported")}</p>
      ) : (
        <>
          <label className="flex items-center gap-3 font-bold">
            <input type="checkbox" className="h-5 w-5 accent-pink" disabled={busy || on === null} checked={!!on} onChange={(e) => void toggle(e.target.checked)} />
            {t("prefs.remindersOn")}
          </label>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <label htmlFor="push-hour" className="font-bold">{t("prefs.remindersHour")}</label>
            <select id="push-hour" className="field !w-auto" value={hour} disabled={!props.me} onChange={(e) => void save({ push_hour: Number(e.target.value) })}>
              {Array.from({ length: 16 }, (_, i) => i + 5).map((h) => (
                <option key={h} value={h}>{clock(h)}</option>
              ))}
            </select>
          </div>
          <label className="mt-4 flex items-center gap-3 font-bold">
            <input type="checkbox" className="h-5 w-5 accent-pink" disabled={!props.me} checked={prefs?.push_details ?? true} onChange={(e) => void save({ push_details: e.target.checked })} />
            {t("prefs.remindersDetails")}
          </label>
          {on && (
            <button className="btn btn-sun mt-4" disabled={busy} onClick={async () => {
              setBusy(true);
              try {
                await apiFetch("/push/test", { method: "POST" });
                props.onNotice(t("prefs.remindersSent"));
              } catch (e) {
                props.onError(e instanceof Error ? e.message : t("common.failed"));
              } finally {
                setBusy(false);
              }
            }}>{t("prefs.remindersTest")}</button>
          )}
        </>
      )}
    </section>
  );
}

/** The Arabic dialect for dictation and replies, and the reading voice. */
export function VoiceSection(props: Props) {
  const { t } = usePrefs();
  const save = usePreferenceSaver(props);
  const { me, setMe } = props;
  const [natural, setNatural] = useState<boolean | null>(null);

  useEffect(() => {
    let live = true;
    voiceStatus().then((v) => live && setNatural(v.speak));
    return () => {
      live = false;
    };
  }, []);

  async function chooseDialect(choice: Dialect | "auto") {
    if (!me) return;
    const before = me;
    const reply_dialect = choice === "auto" ? null : choice;
    setMe({ ...me, reply_dialect });
    try {
      setMe(await apiFetch<UserProfile>("/users/me", { method: "PATCH", body: JSON.stringify({ reply_dialect }) }));
      props.onNotice(t("prefs.saved"));
    } catch (e) {
      setMe(before);
      props.onError(e instanceof Error ? e.message : t("common.failed"));
    }
  }

  const current = me?.reply_dialect ?? "auto";
  return (
    <section className={SECTION}>
      <h2 className="display text-2xl">{t("prefs.voice")}</h2>
      <fieldset className="mt-3">
        <legend className="font-bold">{t("prefs.dialect")}</legend>
        <p className="mb-2 mt-1 text-[14px] text-ink-soft">{t("prefs.dialectHelp")}</p>
        <div className="flex flex-wrap gap-2">
          {DIALECTS.map((option) => (
            <label key={option} className={`flex min-h-11 cursor-pointer items-center gap-2 border-2 border-ink px-4 font-bold ${current === option ? "bg-sun" : "bg-paper-hi"}`}>
              <input type="radio" name="dialect" className="h-4 w-4 accent-pink" disabled={!me} checked={current === option} onChange={() => void chooseDialect(option)} />
              {t(`prefs.dialect.${option}`)}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-5 border-t-2 border-ink/15 pt-4">
        <label className="flex items-center gap-3 font-bold">
          <input type="checkbox" className="h-5 w-5 accent-pink" disabled={!me || natural === false} checked={natural !== false && (me?.ui_preferences?.natural_voice ?? true)} onChange={(e) => {
            setPreferNatural(e.target.checked);
            void save({ natural_voice: e.target.checked });
          }} />
          {t("prefs.natural")}
        </label>
        <p className="mt-2 text-[14px] text-ink-soft">{natural === false ? t("prefs.naturalOff") : t("prefs.naturalHelp")}</p>
      </div>
    </section>
  );
}

/** Text size, contrast and motion for the whole app. */
export function AccessibilitySection(props: Props) {
  const { t, locale } = usePrefs();
  const save = usePreferenceSaver(props);
  const prefs = props.me?.ui_preferences;
  const current = {
    scale: prefs?.text_scale ?? 1,
    contrast: prefs?.high_contrast ?? false,
    calm: prefs?.reduce_motion ?? false,
  };

  function change(next: Partial<typeof current>) {
    const merged = { ...current, ...next };
    applyA11y(merged);
    void save({ text_scale: merged.scale, high_contrast: merged.contrast, reduce_motion: merged.calm });
  }

  return (
    <section className={SECTION}>
      <h2 className="display text-2xl">{t("prefs.a11y")}</h2>
      <fieldset className="mt-3">
        <legend className="font-bold">{t("prefs.textSize")}</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {TEXT_SCALES.map((scale) => (
            <label key={scale} className={`flex min-h-11 cursor-pointer items-center gap-2 border-2 border-ink px-4 font-bold ${current.scale === scale ? "bg-sun" : "bg-paper-hi"}`}>
              <input type="radio" name="text-scale" className="h-4 w-4 accent-pink" disabled={!props.me} checked={current.scale === scale} onChange={() => change({ scale })} />
              <span style={{ fontSize: `${scale}em` }}>{t("prefs.size", { n: new Intl.NumberFormat(intlTag(locale)).format(Math.round(scale * 100)) })}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-5 space-y-4 border-t-2 border-ink/15 pt-4">
        <div>
          <label className="flex items-center gap-3 font-bold">
            <input type="checkbox" className="h-5 w-5 accent-pink" disabled={!props.me} checked={current.contrast} onChange={(e) => change({ contrast: e.target.checked })} />
            {t("prefs.contrast")}
          </label>
          <p className="mt-1 text-[14px] text-ink-soft">{t("prefs.contrastHelp")}</p>
        </div>
        <div>
          <label className="flex items-center gap-3 font-bold">
            <input type="checkbox" className="h-5 w-5 accent-pink" disabled={!props.me} checked={current.calm} onChange={(e) => change({ calm: e.target.checked })} />
            {t("prefs.motion")}
          </label>
          <p className="mt-1 text-[14px] text-ink-soft">{t("prefs.motionHelp")}</p>
        </div>
      </div>
    </section>
  );
}

/** Which specialists appear on Home, the Team page and the pickers. */
export function TeammatesSection(props: Props) {
  const { t } = usePrefs();
  const save = usePreferenceSaver(props);
  const { agents } = useAgents();
  const name = useAgentName();
  const hidden = props.me?.ui_preferences?.hidden_agents ?? [];

  return (
    <section className={SECTION}>
      <h2 className="display text-2xl">{t("prefs.teammates")}</h2>
      <p className="my-3 text-ink-soft">{t("prefs.teammatesHelp")}</p>
      <ul className="grid gap-2 sm:grid-cols-2">
        {agents.filter((a) => !a.is_assistant).map((agent) => (
          <li key={agent.id}>
            <label className="flex min-h-11 items-center gap-3 font-bold">
              <input type="checkbox" className="h-5 w-5 accent-pink" disabled={!props.me} checked={!hidden.includes(agent.id)} onChange={(e) =>
                void save({ hidden_agents: e.target.checked ? hidden.filter((id) => id !== agent.id) : [...hidden, agent.id] })
              } />
              {name(agent)}
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}
