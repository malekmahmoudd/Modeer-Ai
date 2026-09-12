"use client";

import { useState } from "react";

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
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState("");

  return (
    <div>
      <p className="my-3 text-ink-soft">
        If you ever lose your password, one of these codes gets you back in. Each works once. Keep
        them somewhere safe and private — they will not be shown again.
      </p>
      <ol className="my-4 grid grid-cols-2 gap-2 border-2 border-ink bg-paper p-4 font-mono text-[15px] font-bold tracking-wide text-ink">
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
            setCopied("Copied. Paste them somewhere safe.");
          } catch {
            setCopied("Copying isn't available here — write them down instead.");
          }
        }}
      >
        Copy codes
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
        I&apos;ve saved these codes
      </label>
      <button type="button" disabled={!saved} className="btn btn-pink mt-4 w-full" onClick={onDone}>
        {doneLabel}
      </button>
    </div>
  );
}
