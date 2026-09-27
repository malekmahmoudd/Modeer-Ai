"use client";

import { useState } from "react";

import { Drawer } from "@/components/design/Drawer";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/primitives";
import { apiFetch } from "@/lib/api";
import { categoryLabel } from "@/lib/format";
import { usePrefs } from "@/lib/i18n";
import { importText } from "@/lib/importChats";

interface Found {
  category: string;
  key: string;
  value: string;
  sensitive: boolean;
  replaces: boolean;
}

/**
 * Bring what another assistant knew: paste its memory list or notes, or pick a
 * ChatGPT or Claude export file. The facts found are listed; only the ticked
 * ones are saved, as your own. Sensitive ones start unticked.
 */
export function ImportMemories({ onSaved }: { onSaved: () => void }) {
  const { t, tn } = usePrefs();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState("");
  const [busy, setBusy] = useState<"" | "reading" | "saving">("");
  const [error, setError] = useState("");
  const [found, setFound] = useState<Found[] | null>(null);
  const [ticked, setTicked] = useState<Set<string>>(new Set());
  const [truncated, setTruncated] = useState(false);

  function reset() {
    setText("");
    setFileName("");
    setFound(null);
    setError("");
    setTicked(new Set());
  }

  async function readFile(file: File) {
    setError("");
    if (file.size > 60 * 1024 * 1024) {
      setError(t("import.tooBig"));
      return;
    }
    setFileName(file.name);
    setText(importText(await file.text()));
  }

  async function find() {
    setBusy("reading");
    setError("");
    try {
      const result = await apiFetch<{ facts: Found[]; truncated: boolean }>("/memory/import/preview", {
        method: "POST",
        body: JSON.stringify({ text: importText(text) }),
      });
      setFound(result.facts);
      setTruncated(result.truncated);
      setTicked(new Set(result.facts.filter((f) => !f.sensitive).map((f) => f.key)));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.failed"));
    } finally {
      setBusy("");
    }
  }

  async function save() {
    if (!found) return;
    setBusy("saving");
    setError("");
    try {
      const facts = found.filter((f) => ticked.has(f.key)).map(({ category, key, value }) => ({ category, key, value }));
      await apiFetch("/memory/import/apply", { method: "POST", body: JSON.stringify({ facts }) });
      onSaved();
      setOpen(false);
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.failed"));
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <button className="btn mb-5 !min-h-[42px] !text-[13.5px]" onClick={() => setOpen(true)}>
        <Icon name="download" size={16} /> {t("import.open")}
      </button>
      {open && (
        <Drawer title={t("import.title")} onClose={() => !busy && setOpen(false)}>
          {!found ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (text.trim().length >= 20) void find();
              }}
            >
              <p className="mb-3 text-ink-soft">{t("import.help")}</p>
              <details className="mb-4 text-[14px]">
                <summary className="cursor-pointer font-bold">{t("import.how")}</summary>
                <ul className="ms-5 mt-2 list-disc space-y-1 text-ink-soft">
                  <li>{t("import.howChatgptMemory")}</li>
                  <li>{t("import.howChatgptExport")}</li>
                  <li>{t("import.howClaude")}</li>
                </ul>
              </details>
              <label htmlFor="import-text" className="block font-bold">{t("import.paste")}</label>
              <textarea id="import-text" dir="auto" rows={8} className="field mt-1 w-full" value={text} onChange={(e) => { setText(e.target.value); setFileName(""); }} />
              <label className="mt-3 block font-bold">
                {t("import.file")}
                <input type="file" accept=".json,.txt,.md" className="mt-1 block w-full text-[14px]" onChange={(e) => { const file = e.target.files?.[0]; if (file) void readFile(file); }} />
              </label>
              {fileName && <p className="mt-2 text-[13px] font-semibold text-ink-soft">{t("import.fileRead", { name: fileName })}</p>}
              <p className="mt-3 text-[13px] text-ink-soft">{t("import.privacy")}</p>
              {error && <p role="alert" className="mt-3 font-semibold text-pink-deep">{error}</p>}
              <button className="btn btn-pink mt-4" disabled={!!busy || text.trim().length < 20}>
                {busy === "reading" ? <Spinner /> : null} {t("import.find")}
              </button>
            </form>
          ) : (
            <div>
              {found.length === 0 ? (
                <p className="font-semibold">{t("import.none")}</p>
              ) : (
                <>
                  <p className="mb-3 text-ink-soft">{t("import.confirm")}</p>
                  <ul className="space-y-2">
                    {found.map((f) => (
                      <li key={f.key}>
                        <label className="flex items-start gap-3 border-2 border-ink/25 p-2.5">
                          <input type="checkbox" className="mt-1 h-5 w-5 shrink-0 accent-pink" checked={ticked.has(f.key)} onChange={() => {
                            const next = new Set(ticked);
                            if (next.has(f.key)) next.delete(f.key);
                            else next.add(f.key);
                            setTicked(next);
                          }} />
                          <span className="min-w-0">
                            <span className="block text-[12px] font-black uppercase tracking-wide text-ink-faint">{categoryLabel(f.category)}</span>
                            <span className="block font-semibold" dir="auto">{f.value}</span>
                            {f.sensitive && <span className="block text-[12.5px] font-bold text-pink-deep">{t("import.sensitive")}</span>}
                            {f.replaces && <span className="block text-[12.5px] font-bold text-ink-soft">{t("import.replaces")}</span>}
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {truncated && <p className="mt-3 text-[13px] text-ink-soft">{t("import.truncated")}</p>}
              {error && <p role="alert" className="mt-3 font-semibold text-pink-deep">{error}</p>}
              <div className="mt-4 flex flex-wrap gap-2">
                {found.length > 0 && (
                  <button className="btn btn-pink" disabled={!!busy || ticked.size === 0} onClick={() => void save()}>
                    {busy === "saving" ? t("common.saving") : tn("import.save", ticked.size)}
                  </button>
                )}
                <button className="btn" disabled={!!busy} onClick={() => setFound(null)}>{t("templates.back")}</button>
              </div>
            </div>
          )}
        </Drawer>
      )}
    </>
  );
}
