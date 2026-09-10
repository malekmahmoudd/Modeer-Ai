"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

export default function LoginPage() {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <div className="min-h-dvh grid place-items-center bg-paper p-6">
    <form className="w-full max-w-md border-2 border-ink bg-paper-hi p-8 shadow-pop" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError("");
      try { await apiFetch("/auth/login", {method: "POST", body: JSON.stringify({access_key: key})}); window.location.assign("/"); }
      catch (err) { setError(err instanceof Error ? err.message : "Could not sign in"); setBusy(false); }
    }}>
      <p className="eyebrow">Your personal AI team</p>
      <h1 className="display text-4xl my-4">Welcome back.</h1>
      <p className="mb-6 text-ink-soft">Use your private access key to meet your team.</p>
      <label htmlFor="access-key" className="block mb-2">Access key</label>
      <input id="access-key" type="password" autoComplete="current-password" required minLength={32} className="field" value={key} onChange={e => setKey(e.target.value)} />
      {error && <p role="alert" className="my-3 text-pink-deep">{error}</p>}
      <button disabled={busy} className="btn btn-pink mt-5 w-full">{busy ? "Signing in…" : "Meet your team"}</button>
    </form>
  </div>;
}
