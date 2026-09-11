"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

export default function AccountPage() {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirm, setConfirm] = useState("");
  async function run(action: string, work: () => Promise<void>) {
    if (busy) return;
    setBusy(action); setError(""); setNotice("");
    try { await work(); }
    catch (e) { setError(e instanceof Error ? e.message : "Please try again."); }
    finally { setBusy(""); }
  }
  return <div className="max-w-2xl space-y-7 pb-8">
    <div><p className="eyebrow">Your account</p><h1 className="display mt-2 text-4xl sm:text-5xl">You’re in control.</h1>
      <p className="mt-4 text-ink-soft">Manage your data and the devices signed in to your team.</p></div>
    {error && <p role="alert" className="border-2 border-ink bg-paper-hi p-4 text-pink-deep">{error}</p>}
    {notice && <p role="status" className="border-2 border-ink bg-sun-pale p-4">{notice}</p>}
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">Keep a copy.</h2>
      <p className="my-3 text-ink-soft">Download your profile, conversations, saved memories, goals and briefings in one file. Keep it somewhere private.</p>
      <button disabled={!!busy} className="btn btn-pink" onClick={() => run("export", async () => {
        const data = await apiFetch<unknown>("/users/me/export");
        const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: "application/json"}));
        const a = document.createElement("a"); a.href = url; a.download = "modeer-export.json"; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setNotice("Your export is ready. Check your downloads.");
      })}>{busy === "export" ? "Preparing your copy…" : "Download my data"}</button>
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">Your devices.</h2>
      <p className="my-3 text-ink-soft">Sign out on every device, including this one. Your invitation key still works. If it is lost or exposed, contact the person who invited you for a replacement.</p>
      <button disabled={!!busy} className="btn btn-sun" onClick={() => {
        if (!window.confirm("Sign out on every device, including this one?")) return;
        void run("sessions", async () => { await apiFetch("/auth/sign-out-everywhere", {method:"POST"}); window.location.assign("/login"); });
      }}>{busy === "sessions" ? "Signing out…" : "Sign out every device"}</button>
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">Delete my account.</h2>
      <p className="my-3 text-ink-soft">Permanently remove your account, chats, memories and goals from Modeer’s live database. This cannot be undone. Existing backups expire on the operator’s retention schedule, normally within 30 days.</p>
      <form onSubmit={e => { e.preventDefault(); if (confirm !== "DELETE") return; void run("delete", async () => {
        await apiFetch("/users/me/delete", {method:"POST", body:JSON.stringify({confirm})}); window.location.assign("/login?deleted=1");
      }); }}>
        <label htmlFor="delete-confirm" className="block font-bold mb-2">Type DELETE to confirm</label>
        <input id="delete-confirm" value={confirm} onChange={e => setConfirm(e.target.value)} autoComplete="off" className="field w-full" disabled={!!busy} />
        <button disabled={!!busy || confirm !== "DELETE"} className="btn btn-pink mt-4">{busy === "delete" ? "Deleting…" : "Permanently delete my account"}</button>
      </form>
    </section>
    <Link href="/privacy" className="inline-block min-h-11 py-2 underline font-bold">Privacy & your data</Link>
  </div>;
}
