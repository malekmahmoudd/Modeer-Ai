"use client";

import { useState } from "react";
import { Drawer } from "./Drawer";
import { useDesignText } from "./text";
import { savePreferences, type DesignPreferences } from "@/lib/design";
export function ReadingDesk({
  prefs,
  onChange,
  onFocus
}: {
  prefs: DesignPreferences;
  onChange: (p: DesignPreferences) => void;
  onFocus: () => void;
}) {
  const t = useDesignText();
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  return <><button className="btn shrink-0" onClick={() => setOpen(true)}>{t("reading")}</button>{open && <Drawer title={t("reading")} onClose={() => setOpen(false)}>
    {([['reading_size', 'size', 14, 24, 1, 16], ['reading_spacing', 'spacing', 1.4, 2.4, .05, 1.85], ['reading_width', 'width', 480, 960, 40, 720]] as const).map(([key, label, min, max, step, fallback]) => <label key={key} className="mb-6 block">{t(label)}: {prefs[key] ?? fallback}<input className="mt-2 block w-full accent-pink" type="range" min={min} max={max} step={step} value={prefs[key] ?? fallback} onChange={e => onChange({
          ...prefs,
          [key]: Number(e.target.value)
        })} /></label>)}
    <div className="design-actions"><button className="btn btn-pink" disabled={busy} onClick={async () => {
          setBusy(true);
          setErr("");
          try {
            await savePreferences(prefs);
            setOpen(false);
          } catch {
            setErr(t("error"));
          } finally {
            setBusy(false);
          }
        }}>{t("save")}</button><button className="btn" onClick={() => {
          setOpen(false);
          onFocus();
        }}>{t("focus")}</button><button className="btn" onClick={() => onChange({
          reading_size: 16,
          reading_spacing: 1.85,
          reading_width: 720
        })}>{t("reset")}</button></div>{err && <p role="alert">{err}</p>}
  </Drawer>}</>;
}
