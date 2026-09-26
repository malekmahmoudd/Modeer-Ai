"use client";

import qrcode from "qrcode-generator";
import { useMemo, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/primitives";
import { apiFetch, useApi } from "@/lib/api";
import { formatNumber, relativeTime } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import type { AccountSecurity, Allowance, SignedInDevice } from "@/types";

const card = "border-2 border-ink bg-paper-hi p-5 shadow-pop-xs";

/** How much of today's AI allowance this account has used. */
export function UsageSection() {
  const { t, tn } = usePrefs();
  const { data } = useApi<Allowance>("/usage/me");
  if (!data) return null;
  const pct = data.limit ? Math.min(100, Math.round((data.used / data.limit) * 100)) : 0;
  return (
    <section className={card}>
      <h2 className="display text-2xl">{t("account.usage")}</h2>
      <p className="my-3 text-ink-soft">{t("account.usageHelp")}</p>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[28px] font-black leading-none text-ink">{t("account.usedPct", { pct: formatNumber(pct) })}</p>
        <p className="text-[14px] font-semibold text-ink-soft">{tn("usage.leftMessages", data.messages_left)}</p>
      </div>
      <div
        className="relative mt-3 h-3 overflow-hidden rounded-full border-2 border-ink bg-paper-lo"
        role="meter"
        aria-label={t("usage.title")}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={t("account.usedPct", { pct })}
      >
        <span className={`absolute inset-y-0 start-0 ${pct >= 85 ? "bg-pink" : "bg-sun-deep"}`} style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-[13px] text-ink-faint">
        {t("account.usedOf", { used: formatNumber(data.used), limit: formatNumber(data.limit) })} · {t("usage.resets")}
      </p>
    </section>
  );
}

/** Every device signed in to this account, each with its own sign-out. */
export function DevicesSection({ onNotice }: { onNotice: (message: string) => void }) {
  const { t } = usePrefs();
  const { data, loading, error, refetch } = useApi<SignedInDevice[]>("/auth/sessions");
  const [busy, setBusy] = useState("");

  const label = (d: SignedInDevice) =>
    d.browser && d.system
      ? t("account.deviceOn", { browser: d.browser, system: d.system })
      : d.browser || d.system || t("account.deviceUnknown");

  async function signOut(device: SignedInDevice) {
    setBusy(device.id);
    try {
      await apiFetch(`/auth/sessions/${device.id}`, { method: "DELETE" });
      if (device.current) {
        window.location.assign("/login");
        return;
      }
      onNotice(t("account.deviceSignedOut"));
      refetch();
    } catch (e) {
      onNotice(e instanceof Error ? e.message : t("common.failed"));
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      <h3 className="font-bold">{t("account.devicesList")}</h3>
      {loading && <Spinner />}
      {error && <p role="alert" className="text-pink-deep">{error}</p>}
      <ul className="mt-2 flex flex-col gap-2">
        {(data ?? []).map((d) => (
          <li key={d.id} className="flex flex-wrap items-center gap-3 border-2 border-ink bg-paper px-3 py-2.5">
            <span className="min-w-0 flex-1">
              <span className="block font-bold text-ink">
                {label(d)}
                {d.current && (
                  <span className="ms-2 border border-ink bg-sun px-1.5 py-0.5 text-[11px] font-black uppercase tracking-wide">
                    {t("account.thisDevice")}
                  </span>
                )}
              </span>
              <span className="block text-[12.5px] text-ink-soft">
                {t("account.lastSeen", { when: relativeTime(d.last_seen_at ?? d.signed_in_at) })}
                {d.network && <> · {t("account.network")} <bdi dir="ltr">{d.network}</bdi></>}
              </span>
            </span>
            <button
              className="btn !min-h-[40px] shrink-0 !text-[13px]"
              disabled={!!busy}
              aria-label={t("account.signOutDeviceLabel", { device: label(d) })}
              onClick={() => signOut(d)}
            >
              {busy === d.id ? <Spinner /> : t("account.signOutDevice")}
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[13px] text-ink-faint">{t("account.devicesNote")}</p>
    </div>
  );
}

/** A QR code drawn as SVG squares: no image request, nothing to allow in the CSP. */
function QrCode({ text, label }: { text: string; label: string }) {
  const cells = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    const size = qr.getModuleCount();
    const dark: string[] = [];
    for (let row = 0; row < size; row++) {
      for (let col = 0; col < size; col++) if (qr.isDark(row, col)) dark.push(`M${col} ${row}h1v1h-1z`);
    }
    return { size, path: dark.join("") };
  }, [text]);
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`-2 -2 ${cells.size + 4} ${cells.size + 4}`}
      className="h-44 w-44 border-2 border-ink bg-white"
      shapeRendering="crispEdges"
    >
      <path d={cells.path} fill="#151714" />
    </svg>
  );
}

/** Two-step sign-in: set up with a QR code, confirm with the first code. */
export function TwoStepSection({
  security,
  onChanged,
  onNotice,
}: {
  security: AccountSecurity | null;
  onChanged: () => void;
  onNotice: (message: string) => void;
}) {
  const { t } = usePrefs();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [setup, setSetup] = useState<{ secret: string; uri: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.failed"));
    } finally {
      setBusy(false);
    }
  }

  if (!security) return null;
  const on = Boolean(security.two_factor);

  return (
    <section className={card}>
      <h2 className="display text-2xl">{t("account.twoStep")}</h2>
      <p className="my-3 text-ink-soft">
        {on ? t("account.twoStepOnHelp") : security.has_password ? t("account.twoStepOffHelp") : t("account.twoStepNeedsPassword")}
      </p>
      {error && <p role="alert" className="mb-3 font-semibold text-pink-deep">{error}</p>}

      {!on && security.has_password && !setup && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              setSetup(await apiFetch<{ secret: string; uri: string }>("/auth/2fa/setup", { method: "POST", body: JSON.stringify({ password }) }));
              setPassword("");
            });
          }}
        >
          <label htmlFor="twostep-password" className="mb-2 block font-bold">{t("account.confirmPassword")}</label>
          <input id="twostep-password" type="password" autoComplete="current-password" required className="field w-full" value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} />
          <button disabled={busy} className="btn btn-pink mt-4">
            <Icon name="check" size={16} /> {t("account.twoStepStart")}
          </button>
        </form>
      )}

      {!on && setup && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await apiFetch("/auth/2fa/enable", { method: "POST", body: JSON.stringify({ code }) });
              setSetup(null);
              setCode("");
              onNotice(t("account.twoStepEnabled"));
              onChanged();
            });
          }}
        >
          <p className="mb-3 font-semibold">{t("account.scan")}</p>
          <div className="flex flex-wrap items-start gap-4">
            <QrCode text={setup.uri} label={t("account.scan")} />
            <div className="min-w-0 flex-1">
              <p className="eyebrow">{t("account.setupKey")}</p>
              <p dir="ltr" className="mt-1 break-all border-2 border-ink bg-paper p-2 font-mono text-[14px] font-bold tracking-wider">
                {setup.secret.replace(/(.{4})/g, "$1 ").trim()}
              </p>
              <a href={setup.uri} className="mt-2 inline-block text-[13px] font-bold underline decoration-pink decoration-2 underline-offset-4">
                {t("account.openApp")}
              </a>
            </div>
          </div>
          <label htmlFor="twostep-code" className="mb-2 mt-4 block font-bold">{t("account.enterCode")}</label>
          <input id="twostep-code" dir="ltr" inputMode="numeric" autoComplete="one-time-code" required minLength={6} maxLength={8} className="field w-40 font-mono tracking-widest" value={code} onChange={(e) => setCode(e.target.value)} disabled={busy} />
          <div className="mt-4 flex gap-2">
            <button disabled={busy} className="btn btn-pink">{t("account.turnOn")}</button>
            <button type="button" className="btn" onClick={() => { setSetup(null); setCode(""); }}>{t("common.cancel")}</button>
          </div>
        </form>
      )}

      {on && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              await apiFetch("/auth/2fa/disable", { method: "POST", body: JSON.stringify({ password, code }) });
              setPassword("");
              setCode("");
              onNotice(t("account.twoStepDisabled"));
              onChanged();
            });
          }}
        >
          <label htmlFor="off-password" className="mb-2 block font-bold">{t("common.password")}</label>
          <input id="off-password" type="password" autoComplete="current-password" required className="field w-full" value={password} onChange={(e) => setPassword(e.target.value)} disabled={busy} />
          <label htmlFor="off-code" className="mb-2 mt-4 block font-bold">{t("account.codeOrRecovery")}</label>
          <input id="off-code" dir="ltr" autoComplete="one-time-code" required minLength={6} maxLength={40} className="field w-full font-mono" value={code} onChange={(e) => setCode(e.target.value)} disabled={busy} />
          <button disabled={busy} className="btn btn-sun mt-4">{t("account.turnOff")}</button>
        </form>
      )}
    </section>
  );
}
