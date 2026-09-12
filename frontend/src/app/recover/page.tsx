"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

export default function RecoverPage() {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [left, setLeft] = useState<number | null>(null);

  return <div className="min-h-dvh grid place-items-center bg-paper p-6">
    <div className="w-full max-w-md border-2 border-ink bg-paper-hi p-8 shadow-pop">
      <p className="eyebrow">Get back in</p>
      {left !== null ? <div role="status">
        <h1 className="display text-4xl my-4">You’re back in.</h1>
        <p className="mb-2 text-ink-soft">Your new password is set, and any other device has been signed out.</p>
        <p className="mb-6 text-ink-soft">
          You have {left} recovery {left === 1 ? "code" : "codes"} left.
          {left <= 3 && " Make a fresh set from your Account page."}
        </p>
        <button type="button" className="btn btn-pink w-full" onClick={() => window.location.assign(left <= 3 ? "/account" : "/")}>
          {left <= 3 ? "Go to my account" : "Meet your team"}
        </button>
      </div> : <form onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError("");
        try {
          const result = await apiFetch<{ recovery_codes_left: number }>("/auth/recover", {method: "POST", body: JSON.stringify({email, code, new_password: password})});
          setLeft(result.recovery_codes_left);
        } catch (err) { setError(err instanceof Error ? err.message : "Could not reset your password"); }
        finally { setBusy(false); }
      }}>
        <h1 className="display text-4xl my-4">Use a recovery code.</h1>
        <p className="mb-6 text-ink-soft">Enter your email, one of the recovery codes you saved when you signed up, and a new password.</p>
        <label htmlFor="email" className="block mb-2">Email</label>
        <input id="email" type="email" autoComplete="email" required className="field" value={email} onChange={e => setEmail(e.target.value)} />
        <label htmlFor="code" className="block mb-2 mt-4">Recovery code</label>
        <input id="code" autoComplete="one-time-code" required minLength={8} maxLength={40} spellCheck={false} className="field font-mono" value={code} onChange={e => setCode(e.target.value)} />
        <label htmlFor="new-password" className="block mb-2 mt-4">New password</label>
        <input id="new-password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} aria-describedby="password-hint" className="field" value={password} onChange={e => setPassword(e.target.value)} />
        <p id="password-hint" className="mt-2 text-[13px] text-ink-soft">At least 10 characters.</p>
        {error && <p role="alert" className="my-3 text-pink-deep">{error}</p>}
        <button disabled={busy} className="btn btn-pink mt-5 w-full">{busy ? "Checking…" : "Reset password and sign in"}</button>
        <div className="mt-5 space-y-1 text-sm">
          <Link href="/login" className="block py-2 underline">Remembered it? Sign in</Link>
          <p className="py-2 text-ink-soft">Signed in with an invitation key and never set a password? Ask the person who invited you.</p>
        </div>
      </form>}
    </div>
  </div>;
}
