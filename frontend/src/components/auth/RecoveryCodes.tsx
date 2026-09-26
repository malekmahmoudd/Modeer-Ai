"use client";

import { useState } from "react";

import { usePrefs } from "@/lib/i18n";

/** Shows freshly issued recovery codes — the only time they are ever visible. */
export function RecoveryCodes({
  codes,
  onDone,
  doneLabel = "Continue",
}: {
  codes: string[];
  onDone: () => void;
  doneLabel?: string;
}) {
  const { t } = usePrefs();
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState("");

  return (
    <div>
      <p className="my-3 text-ink-soft">{t("codes.help")}</p>
      <ol dir="ltr" className="my-4 grid grid-cols-2 gap-2 border-2 border-ink bg-paper p-4 font-mono text-[15px] font-bold tracking-wide text-ink">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ol>
      <button
        type="button"
        className="btn btn-sun"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(codes.join("\n"));
            setCopied(t("codes.copied"));
          } catch {
            setCopied(t("codes.cantCopy"));
          }
        }}
      >
        {t("codes.copy")}
      </button>
      {copied && (
        <p role="status" className="mt-2 text-[13.5px] font-semibold text-ink-soft">
          {copied}
        </p>
      )}
      <label className="mt-5 flex items-center gap-3 font-bold">
        <input
          type="checkbox"
          className="h-5 w-5 accent-pink"
          checked={saved}
          onChange={(e) => setSaved(e.target.checked)}
        />
        {t("codes.saved")}
      </label>
      <button type="button" disabled={!saved} className="btn btn-pink mt-4 w-full" onClick={onDone}>
        {doneLabel}
      </button>
    </div>
  );
}
