"use client";

import Link from "next/link";
import { useState } from "react";
import { RecoveryCodes } from "@/components/auth/RecoveryCodes";
import { apiFetch, useApi } from "@/lib/api";
import type { AccountSecurity, UserProfile } from "@/types";

export default function AccountPage() {
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
    catch (e) { setError(e instanceof Error ? e.message : "Please try again."); }
    finally { setBusy(""); }
  }
  const hasPassword = security?.has_password ?? false;
  return <div className="max-w-2xl space-y-7 pb-8">
    <div><p className="eyebrow">Your account</p><h1 className="display mt-2 text-4xl sm:text-5xl">You’re in control.</h1>
      <p className="mt-4 text-ink-soft">Manage what Leo learns, how you sign in, your data and your devices.</p></div>
    {error && <p role="alert" className="border-2 border-ink bg-paper-hi p-4 text-pink-deep">{error}</p>}
    {notice && <p role="status" className="border-2 border-ink bg-sun-pale p-4">{notice}</p>}
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">What Leo learns.</h2>
      <p className="my-3 text-ink-soft">When this is on, Leo picks up lasting facts from what you tell your team. When it is off, nothing is learned from your messages. What you save or edit on the Memory page still works, and nothing already saved is removed.</p>
      <label className="flex items-center gap-3 font-bold">
        <input type="checkbox" className="h-5 w-5 accent-pink" disabled={!me || !!busy} checked={me?.memory_auto ?? true} onChange={e => {
          if (!me) return;
          const on = e.target.checked;
          setMe({...me, memory_auto: on}); // show the choice at once; undone below if saving fails
          void run("memory", async () => {
            try {
              const updated = await apiFetch<UserProfile>("/users/me", {method: "PATCH", body: JSON.stringify({memory_auto: on})});
              setMe(updated);
              setNotice(on ? "Leo will learn from your messages again." : "Leo will no longer learn from your messages.");
            } catch (err) { setMe({...me, memory_auto: !on}); throw err; }
          });
        }} />
        Learn from my messages automatically
      </label>
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">Signing in.</h2>
      {freshCodes ? <RecoveryCodes codes={freshCodes} doneLabel="Done" onDone={() => { setFreshCodes(null); refetchSecurity(); }} /> : <>
        <p className="my-3 text-ink-soft">{hasPassword
          ? "Change your password. Every other device signs out; this one stays signed in."
          : "You sign in with an invitation key. Set a password to sign in with your email instead — you’ll get recovery codes in case you ever forget it."}</p>
        <form onSubmit={e => { e.preventDefault(); void run("password", async () => {
          const result = await apiFetch<{ recovery_codes: string[] | null }>("/auth/password", {method: "POST", body: JSON.stringify(hasPassword ? {current_password: currentPassword, new_password: newPassword} : {new_password: newPassword})});
          setCurrentPassword(""); setNewPassword("");
          if (result.recovery_codes) setFreshCodes(result.recovery_codes);
          else setNotice("Your password is changed. Other devices have been signed out.");
          refetchSecurity();
        }); }}>
          {hasPassword && <>
            <label htmlFor="current-password" className="block font-bold mb-2">Current password</label>
            <input id="current-password" type="password" autoComplete="current-password" required className="field w-full mb-4" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} disabled={!!busy} />
          </>}
          <label htmlFor="new-password" className="block font-bold mb-2">{hasPassword ? "New password" : "Password"}</label>
          <input id="new-password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} aria-describedby="new-password-hint" className="field w-full" value={newPassword} onChange={e => setNewPassword(e.target.value)} disabled={!!busy || !security} />
          <p id="new-password-hint" className="mt-2 text-[13px] text-ink-soft">At least 10 characters.</p>
          <button disabled={!!busy || !security} className="btn btn-pink mt-4">{busy === "password" ? "Saving…" : hasPassword ? "Change password" : "Set password"}</button>
        </form>
        {hasPassword && <div className="mt-6 border-t-2 border-ink/15 pt-5">
          <h3 className="font-bold">Recovery codes</h3>
          <p className="my-2 text-ink-soft">You have {security?.recovery_codes_left ?? 0} of 10 left. Making a new set retires every old code.</p>
          <form onSubmit={e => { e.preventDefault(); void run("codes", async () => {
            const result = await apiFetch<{ recovery_codes: string[] }>("/auth/recovery-codes", {method: "POST", body: JSON.stringify({password: codesPassword})});
            setCodesPassword(""); setFreshCodes(result.recovery_codes);
          }); }}>
            <label htmlFor="codes-password" className="block font-bold mb-2">Confirm with your password</label>
            <input id="codes-password" type="password" autoComplete="current-password" required className="field w-full" value={codesPassword} onChange={e => setCodesPassword(e.target.value)} disabled={!!busy} />
            <button disabled={!!busy} className="btn btn-sun mt-4">{busy === "codes" ? "Making codes…" : "Make new recovery codes"}</button>
          </form>
        </div>}
      </>}
    </section>
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
      <p className="my-3 text-ink-soft">{hasPassword
        ? "Sign out on every device, including this one. Your password still works. If you think someone else knows it, change it above."
        : "Sign out on every device, including this one. Your invitation key still works. If it is lost or exposed, contact the person who invited you for a replacement."}</p>
      <button disabled={!!busy} className="btn btn-sun" onClick={() => {
        if (!window.confirm("Sign out on every device, including this one?")) return;
        void run("sessions", async () => { await apiFetch("/auth/sign-out-everywhere", {method:"POST"}); window.location.assign("/login"); });
      }}>{busy === "sessions" ? "Signing out…" : "Sign out every device"}</button>
    </section>
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs">
      <h2 className="display text-2xl">Delete my account.</h2>
      <p className="my-3 text-ink-soft">Permanently remove your account, chats, memories and goals from Fareeq’s live database. This cannot be undone. Existing backups expire on the operator’s retention schedule, normally within 30 days.</p>
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
