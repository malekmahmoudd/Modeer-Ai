"use client";

import Link from "next/link";
import { useState } from "react";
import { RecoveryCodes } from "@/components/auth/RecoveryCodes";
import { apiFetch, useApi } from "@/lib/api";
import { usePrefs, type Locale } from "@/lib/i18n";
import { clearDrafts } from "@/lib/offline";
import type { AccountSecurity, UserProfile } from "@/types";

export default function AccountPage() {
  const { t, locale, setLocale, dataSaver, setDataSaver } = usePrefs();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState("");
  const { data: me, setData: setMe } = useApi<UserProfile>("/users/me");
  const { data: security, refetch: refetchSecurity } = useApi<AccountSecurity>("/auth/account");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [codesPassword, setCodesPassword] = useState("");
  const [freshCodes, setFreshCodes] = useState<string[] | null>(null);
  async function run(action: string, work: () => Promise<void>) {
    if (busy) return;
    setBusy(action); setError(""); setNotice("");
    try { await work(); }
    catch (e) { setError(e instanceof Error ? e.message : t("account.retry")); }
    finally { setBusy(""); }
  }
  function chooseLanguage(next: Locale) {
    if (next === locale) return;
    setLocale(next);
    if (me) setMe({ ...me, locale: next });
    apiFetch("/users/me", { method: "PATCH", body: JSON.stringify({ locale: next }) }).catch(() => undefined);
  }
  const hasPassword = security?.has_password ?? false;
  return <div className="max-w-2xl space-y-7 pb-8">
    <div><p className="eyebrow">{t("account.eyebrow")}</p><h1 className="display mt-2 text-4xl sm:text-5xl">{t("account.title")}</h1>
      <p className="mt-4 text-ink-soft">{t("account.lede")}</p></div>
    {error && <p role="alert" className="border-2 border-ink bg-paper-hi p-4 text-pink-deep">{error}</p>}
    {notice && <p role="status" className="border-2 border-ink bg-sun-pale p-4">{notice}</p>}
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">{t("account.learns")}</h2>
      <p className="my-3 text-ink-soft">{t("account.learnsHelp")}</p>
      <label className="flex items-center gap-3 font-bold">
        <input type="checkbox" className="h-5 w-5 accent-pink" disabled={!me || !!busy} checked={me?.memory_auto ?? true} onChange={e => {
          if (!me) return;
          const on = e.target.checked;
          setMe({...me, memory_auto: on}); // show the choice at once; undone below if saving fails
          void run("memory", async () => {
            try {
              const updated = await apiFetch<UserProfile>("/users/me", {method: "PATCH", body: JSON.stringify({memory_auto: on})});
              setMe(updated);
              setNotice(on ? t("account.learnOn") : t("account.learnOff"));
            } catch (err) { setMe({...me, memory_auto: !on}); throw err; }
          });
        }} />
        {t("account.learnToggle")}
      </label>
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">{t("account.appearance")}</h2>
      <fieldset className="mt-3">
        <legend className="font-bold">{t("account.language")}</legend>
        <p className="mb-2 mt-1 text-[14px] text-ink-soft">{t("account.languageHelp")}</p>
        <div className="flex flex-wrap gap-2">
          {(["en", "ar"] as const).map((option) => (
            <label key={option} lang={option} className={`flex min-h-11 cursor-pointer items-center gap-2 border-2 border-ink px-4 font-bold ${locale === option ? "bg-sun" : "bg-paper-hi"}`}>
              <input type="radio" name="locale" className="h-4 w-4 accent-pink" checked={locale === option} onChange={() => chooseLanguage(option)} />
              {option === "en" ? t("account.english") : t("account.arabic")}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="mt-5 border-t-2 border-ink/15 pt-4">
        <label className="flex items-center gap-3 font-bold">
          <input type="checkbox" className="h-5 w-5 accent-pink" checked={dataSaver} onChange={e => {
            setDataSaver(e.target.checked);
            setNotice(e.target.checked ? t("account.saverOn") : t("account.saverOff"));
          }} />
          {t("account.saver")}
        </label>
        <p className="mt-2 text-[14px] text-ink-soft">{t("account.saverHelp")}</p>
      </div>
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">{t("account.signingIn")}</h2>
      {freshCodes ? <RecoveryCodes codes={freshCodes} doneLabel={t("common.done")} onDone={() => { setFreshCodes(null); refetchSecurity(); }} /> : <>
        <p className="my-3 text-ink-soft">{hasPassword ? t("account.changeHelp") : t("account.setHelp")}</p>
        <form onSubmit={e => { e.preventDefault(); void run("password", async () => {
          const result = await apiFetch<{ recovery_codes: string[] | null }>("/auth/password", {method: "POST", body: JSON.stringify(hasPassword ? {current_password: currentPassword, new_password: newPassword} : {new_password: newPassword})});
          setCurrentPassword(""); setNewPassword("");
          if (result.recovery_codes) setFreshCodes(result.recovery_codes);
          else setNotice(t("account.changed"));
          refetchSecurity();
        }); }}>
          {hasPassword && <>
            <label htmlFor="current-password" className="block font-bold mb-2">{t("account.current")}</label>
            <input id="current-password" type="password" autoComplete="current-password" required className="field w-full mb-4" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} disabled={!!busy} />
          </>}
          <label htmlFor="new-password" className="block font-bold mb-2">{hasPassword ? t("common.newPassword") : t("common.password")}</label>
          <input id="new-password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} aria-describedby="new-password-hint" className="field w-full" value={newPassword} onChange={e => setNewPassword(e.target.value)} disabled={!!busy || !security} />
          <p id="new-password-hint" className="mt-2 text-[13px] text-ink-soft">{t("common.passwordHint")}</p>
          <button disabled={!!busy || !security} className="btn btn-pink mt-4">{busy === "password" ? t("common.saving") : hasPassword ? t("account.change") : t("account.set")}</button>
        </form>
        {hasPassword && <div className="mt-6 border-t-2 border-ink/15 pt-5">
          <h3 className="font-bold">{t("account.codes")}</h3>
          <p className="my-2 text-ink-soft">{t("account.codesLeft", { n: security?.recovery_codes_left ?? 0 })}</p>
          <form onSubmit={e => { e.preventDefault(); void run("codes", async () => {
            const result = await apiFetch<{ recovery_codes: string[] }>("/auth/recovery-codes", {method: "POST", body: JSON.stringify({password: codesPassword})});
            setCodesPassword(""); setFreshCodes(result.recovery_codes);
          }); }}>
            <label htmlFor="codes-password" className="block font-bold mb-2">{t("account.confirmPassword")}</label>
            <input id="codes-password" type="password" autoComplete="current-password" required className="field w-full" value={codesPassword} onChange={e => setCodesPassword(e.target.value)} disabled={!!busy} />
            <button disabled={!!busy} className="btn btn-sun mt-4">{busy === "codes" ? t("account.makingCodes") : t("account.makeCodes")}</button>
          </form>
        </div>}
      </>}
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">{t("account.copy")}</h2>
      <p className="my-3 text-ink-soft">{t("account.copyHelp")}</p>
      <button disabled={!!busy} className="btn btn-pink" onClick={() => run("export", async () => {
        const data = await apiFetch<unknown>("/users/me/export");
        const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
        const a = document.createElement("a"); a.href = url; a.download = "fareeq-export.json"; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setNotice(t("account.exportReady"));
      })}>{busy === "export" ? t("account.preparing") : t("account.download")}</button>
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">{t("account.devices")}</h2>
      <p className="my-3 text-ink-soft">{hasPassword ? t("account.devicesPassword") : t("account.devicesKey")}</p>
      <button disabled={!!busy} className="btn btn-sun" onClick={() => {
        if (!window.confirm(t("account.signOutAllConfirm"))) return;
        void run("sessions", async () => { await apiFetch("/auth/sign-out-everywhere", {method:"POST"}); clearDrafts(); window.location.assign("/login"); });
      }}>{busy === "sessions" ? t("account.signingOut") : t("account.signOutAll")}</button>
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">{t("account.delete")}</h2>
      <p className="my-3 text-ink-soft">{t("account.deleteHelp")}</p>
      <form onSubmit={e => { e.preventDefault(); if (confirm !== "DELETE") return; void run("delete", async () => {
        await apiFetch("/users/me/delete", {method:"POST", body:JSON.stringify({confirm})}); clearDrafts(); window.location.assign("/login?deleted=1");
      }); }}>
        <label htmlFor="delete-confirm" className="block font-bold mb-2">{t("account.typeDelete")}</label>
        <input id="delete-confirm" dir="ltr" value={confirm} onChange={e => setConfirm(e.target.value)} autoComplete="off" className="field w-full" disabled={!!busy} />
        <button disabled={!!busy || confirm !== "DELETE"} className="btn btn-pink mt-4">{busy === "delete" ? t("account.deleting") : t("account.deleteButton")}</button>
      </form>
    </section>
    <Link href="/privacy" className="inline-block min-h-11 py-2 underline font-bold">{t("common.privacy")}</Link>
  </div>;
}
