"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";

export default function RecoverPage() {
  const { t, tn } = usePrefs();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [left, setLeft] = useState<number | null>(null);

  return <div className="min-h-dvh grid place-items-center bg-paper p-6">
    <div className="w-full max-w-md border-2 border-ink bg-paper-hi p-8 shadow-pop">
      <p className="eyebrow">{t("auth.getBack")}</p>
      {left !== null ? <div role="status">
        <h1 className="display text-4xl my-4">{t("auth.backIn")}</h1>
        <p className="mb-2 text-ink-soft">{t("auth.backInHelp")}</p>
        <p className="mb-6 text-ink-soft">
          {tn("auth.codesLeft", left)}
          {left <= 3 && t("auth.makeFresh")}
        </p>
        <button type="button" className="btn btn-pink w-full" onClick={() => window.location.assign(left <= 3 ? "/account" : "/")}>
          {left <= 3 ? t("auth.goAccount") : t("auth.meetTeam")}
        </button>
      </div> : <form onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError("");
        try {
          const result = await apiFetch<{ recovery_codes_left: number }>("/auth/recover", {method: "POST", body: JSON.stringify({email, code, new_password: password})});
          setLeft(result.recovery_codes_left);
        } catch (err) { setError(err instanceof Error ? err.message : t("auth.resetFailed")); }
        finally { setBusy(false); }
      }}>
        <h1 className="display text-4xl my-4">{t("auth.useCode")}</h1>
        <p className="mb-6 text-ink-soft">{t("auth.useCodeHelp")}</p>
        <label htmlFor="email" className="block mb-2">{t("common.email")}</label>
        <input id="email" dir="ltr" type="email" autoComplete="email" required className="field" value={email} onChange={e => setEmail(e.target.value)} />
        <label htmlFor="code" className="block mb-2 mt-4">{t("auth.code")}</label>
        <input id="code" dir="ltr" autoComplete="one-time-code" required minLength={8} maxLength={40} spellCheck={false} className="field font-mono" value={code} onChange={e => setCode(e.target.value)} />
        <label htmlFor="new-password" className="block mb-2 mt-4">{t("common.newPassword")}</label>
        <input id="new-password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} aria-describedby="password-hint" className="field" value={password} onChange={e => setPassword(e.target.value)} />
        <p id="password-hint" className="mt-2 text-[13px] text-ink-soft">{t("common.passwordHint")}</p>
        {error && <p role="alert" className="my-3 text-pink-deep">{error}</p>}
        <button disabled={busy} className="btn btn-pink mt-5 w-full">{busy ? t("auth.checking") : t("auth.reset")}</button>
        <div className="mt-5 space-y-1 text-sm">
          <Link href="/login" className="block py-2 underline">{t("auth.remembered")}</Link>
          <p className="py-2 text-ink-soft">{t("auth.keyOnly")}</p>
        </div>
      </form>}
    </div>
  </div>;
}
