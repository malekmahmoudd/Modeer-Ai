"use client";

import Link from "next/link";
import { useState } from "react";
import { RecoveryCodes } from "@/components/auth/RecoveryCodes";
import { apiFetch, useApi } from "@/lib/api";
import type { AuthStatus } from "@/types";

export default function SignupPage() {
  const { data: auth, loading } = useApi<AuthStatus>("/auth/status");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);

  return <div className="min-h-dvh grid place-items-center bg-paper p-6">
    <div className="w-full max-w-md border-2 border-ink bg-paper-hi p-8 shadow-pop">
      <p className="eyebrow">Your personal AI team</p>
      {codes ? <>
        <h1 className="display text-4xl my-4">Save your recovery codes.</h1>
        <RecoveryCodes codes={codes} doneLabel="Meet your team" onDone={() => window.location.assign("/agents/modeer?onboarding=1")} />
      </> : !loading && !auth?.signup_enabled ? <>
        <h1 className="display text-4xl my-4">Not open yet.</h1>
        <p className="mb-6 text-ink-soft">New accounts can’t be created right now. If you have an invitation, sign in with it.</p>
        <Link href="/login" className="btn btn-pink w-full">Go to sign in</Link>
      </> : <form onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError("");
        try {
          const result = await apiFetch<{ recovery_codes: string[] }>("/auth/signup", {method: "POST", body: JSON.stringify({display_name: name, email, password})});
          setCodes(result.recovery_codes);
        } catch (err) { setError(err instanceof Error ? err.message : "Could not create your account"); }
        finally { setBusy(false); }
      }}>
        <h1 className="display text-4xl my-4">Meet your team.</h1>
        <p className="mb-6 text-ink-soft">Create your account. It takes a minute.</p>
        <label htmlFor="name" className="block mb-2">What should we call you?</label>
        <input id="name" autoComplete="given-name" required maxLength={60} className="field" value={name} onChange={e => setName(e.target.value)} />
        <label htmlFor="email" className="block mb-2 mt-4">Email</label>
        <input id="email" type="email" autoComplete="email" required className="field" value={email} onChange={e => setEmail(e.target.value)} />
        <label htmlFor="password" className="block mb-2 mt-4">Password</label>
        <input id="password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} aria-describedby="password-hint" className="field" value={password} onChange={e => setPassword(e.target.value)} />
        <p id="password-hint" className="mt-2 text-[13px] text-ink-soft">At least 10 characters. A few unrelated words work well.</p>
        {error && <p role="alert" className="my-3 text-pink-deep">{error}</p>}
        <button disabled={busy} className="btn btn-pink mt-5 w-full">{busy ? "Creating your account…" : "Create my account"}</button>
        <div className="mt-5 space-y-1 text-sm">
          <Link href="/login" className="block py-2 underline">Already have an account? Sign in</Link>
          <Link href="/privacy" className="block py-2 underline">Privacy & your data</Link>
        </div>
      </form>}
    </div>
  </div>;
}
