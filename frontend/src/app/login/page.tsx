"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch, useApi } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";
import type { AuthStatus } from "@/types";

export default function LoginPage() {
  const { data: auth } = useApi<AuthStatus>("/auth/status");
  const { t } = usePrefs();
  const [useKey, setUseKey] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <div className="min-h-dvh grid place-items-center bg-paper p-6">
    <form className="w-full max-w-md border-2 border-ink bg-paper-hi p-8 shadow-pop" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError("");
      const body = useKey ? {access_key: key} : {email, password};
      try { await apiFetch("/auth/login", {method: "POST", body: JSON.stringify(body)}); window.location.assign("/"); }
      catch (err) { setError(err instanceof Error ? err.message : t("auth.signInFailed")); setBusy(false); }
    }}>
      <p className="eyebrow">{t("auth.eyebrow")}</p>
      <h1 className="display text-4xl my-4">{t("auth.welcome")}</h1>
      {useKey ? <>
        <p className="mb-6 text-ink-soft">{t("auth.useKeyHelp")}</p>
        <label htmlFor="access-key" className="block mb-2">{t("auth.accessKey")}</label>
        <input id="access-key" type="password" autoComplete="current-password" required minLength={32} className="field" value={key} onChange={e => setKey(e.target.value)} />
      </> : <>
        <p className="mb-6 text-ink-soft">{t("auth.signInHelp")}</p>
        <label htmlFor="email" className="block mb-2">{t("common.email")}</label>
        <input id="email" dir="ltr" type="email" autoComplete="email" required className="field" value={email} onChange={e => setEmail(e.target.value)} />
        <label htmlFor="password" className="block mb-2 mt-4">{t("common.password")}</label>
        <input id="password" type="password" autoComplete="current-password" required className="field" value={password} onChange={e => setPassword(e.target.value)} />
      </>}
      {error && <p role="alert" className="my-3 text-pink-deep">{error}</p>}
      <button disabled={busy} className="btn btn-pink mt-5 w-full">{busy ? t("auth.signingIn") : t("auth.meetTeam")}</button>
      <div className="mt-5 space-y-1 text-sm">
        {!useKey && <Link href="/recover" className="block py-2 underline">{t("auth.forgot")}</Link>}
        {auth?.signup_enabled && <Link href="/signup" className="block py-2 underline">{t("auth.newHere")}</Link>}
        <button type="button" className="block py-2 text-start underline" onClick={() => { setUseKey(!useKey); setError(""); }}>
          {useKey ? t("auth.useEmail") : t("auth.useKey")}
        </button>
        <Link href="/privacy" className="block py-2 underline">{t("common.privacy")}</Link>
      </div>
    </form>
  </div>;
}
