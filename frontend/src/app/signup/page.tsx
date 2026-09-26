"use client";

import Link from "next/link";
import { useState } from "react";
import { RecoveryCodes } from "@/components/auth/RecoveryCodes";
import { apiFetch, useApi } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";
import type { AuthStatus } from "@/types";

export default function SignupPage() {
  const { data: auth, loading } = useApi<AuthStatus>("/auth/status");
  const { t } = usePrefs();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);

  return <div className="min-h-dvh grid place-items-center bg-paper p-6">
    <div className="w-full max-w-md border-2 border-ink bg-paper-hi p-8 shadow-pop">
      <p className="eyebrow">{t("auth.eyebrow")}</p>
      {codes ? <>
        <h1 className="display text-4xl my-4">{t("auth.saveCodes")}</h1>
        <RecoveryCodes codes={codes} doneLabel={t("auth.meetTeam")} onDone={() => window.location.assign("/agents/modeer?onboarding=1")} />
      </> : !loading && !auth?.signup_enabled ? <>
        <h1 className="display text-4xl my-4">{t("auth.notOpen")}</h1>
        <p className="mb-6 text-ink-soft">{t("auth.notOpenHelp")}</p>
        <Link href="/login" className="btn btn-pink w-full">{t("auth.goSignIn")}</Link>
      </> : <form onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError("");
        try {
          const result = await apiFetch<{ recovery_codes: string[] }>("/auth/signup", {method: "POST", body: JSON.stringify({display_name: name, email, password})});
          setCodes(result.recovery_codes);
        } catch (err) { setError(err instanceof Error ? err.message : t("auth.createFailed")); }
        finally { setBusy(false); }
      }}>
        <h1 className="display text-4xl my-4">{t("auth.meetTitle")}</h1>
        <p className="mb-6 text-ink-soft">{t("auth.createHelp")}</p>
        <label htmlFor="name" className="block mb-2">{t("auth.callYou")}</label>
        <input id="name" dir="auto" autoComplete="given-name" required maxLength={60} className="field" value={name} onChange={e => setName(e.target.value)} />
        <label htmlFor="email" className="block mb-2 mt-4">{t("common.email")}</label>
        <input id="email" dir="ltr" type="email" autoComplete="email" required className="field" value={email} onChange={e => setEmail(e.target.value)} />
        <label htmlFor="password" className="block mb-2 mt-4">{t("common.password")}</label>
        <input id="password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} aria-describedby="password-hint" className="field" value={password} onChange={e => setPassword(e.target.value)} />
        <p id="password-hint" className="mt-2 text-[13px] text-ink-soft">{t("auth.passwordHintLong")}</p>
        {error && <p role="alert" className="my-3 text-pink-deep">{error}</p>}
        <button disabled={busy} className="btn btn-pink mt-5 w-full">{busy ? t("auth.creating") : t("auth.create")}</button>
        <div className="mt-5 space-y-1 text-sm">
          <Link href="/login" className="block py-2 underline">{t("auth.haveAccount")}</Link>
          <Link href="/privacy" className="block py-2 underline">{t("common.privacy")}</Link>
        </div>
      </form>}
    </div>
  </div>;
}
