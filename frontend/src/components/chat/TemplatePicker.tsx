"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { Drawer } from "@/components/design/Drawer";
import { Icon } from "@/components/ui/Icon";
import { apiFetch } from "@/lib/api";
import { usePrefs } from "@/lib/i18n";
import { blanks, fill, STARTERS } from "@/lib/templates";
import type { PromptTemplate } from "@/types";

interface Choice {
  title: string;
  body: string;
  /** Set for the person's own templates, which can be deleted. */
  id?: string;
}

/**
 * Prompts with {blanks}: the starter library and the person's own. Picking one
 * asks for each blank, then puts the filled text in the message box to edit
 * and send; nothing is sent from here.
 */
export function TemplatePicker({
  agentId,
  current,
  disabled,
  onInsert,
}: {
  agentId: string;
  /** What is in the message box now, offered to save as a template. */
  current: string;
  disabled?: boolean;
  onInsert: (text: string) => void;
}) {
  const { t, locale } = usePrefs();
  const [open, setOpen] = useState(false);
  const [own, setOwn] = useState<PromptTemplate[] | null>(null);
  const [chosen, setChosen] = useState<Choice | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saveTitle, setSaveTitle] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => {
    if (!open) return;
    let live = true;
    apiFetch<PromptTemplate[]>(`/templates?agent_id=${encodeURIComponent(agentId)}`)
      .then((rows) => live && setOwn(rows))
      .catch(() => live && setOwn([]));
    return () => {
      live = false;
    };
  }, [open, agentId]);

  function close() {
    setOpen(false);
    setChosen(null);
    setValues({});
    setNote("");
  }

  function choose(choice: Choice) {
    if (!blanks(choice.body).length) {
      onInsert(choice.body);
      close();
      return;
    }
    setChosen(choice);
    setValues({});
  }

  async function saveCurrent() {
    try {
      const row = await apiFetch<PromptTemplate>("/templates", {
        method: "POST",
        body: JSON.stringify({ title: saveTitle.trim(), body: current.trim(), agent_id: agentId }),
      });
      setOwn([...(own ?? []), row]);
      setSaveTitle("");
      setNote(t("templates.saved"));
    } catch (e) {
      setNote(e instanceof Error ? e.message : t("common.failed"));
    }
  }

  async function remove(id: string) {
    await apiFetch(`/templates/${id}`, { method: "DELETE" }).catch(() => undefined);
    setOwn((own ?? []).filter((row) => row.id !== id));
  }

  const starters = STARTERS.filter((s) => s.agent_id === null || s.agent_id === agentId).map((s) => ({
    title: s.title[locale],
    body: s.body[locale],
  }));
  const fields = chosen ? blanks(chosen.body) : [];

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(true)}
        aria-label={t("templates.open")}
        title={t("templates.open")}
        className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-ink-soft transition hover:bg-sun-pale hover:text-ink disabled:opacity-40"
      >
        <Icon name="template" size={20} />
      </button>
      {/* In a portal: the picker sits inside the message box's form, and a form
          inside a form would submit the page instead of filling the box. */}
      {open && createPortal(
        <Drawer title={chosen ? chosen.title : t("templates.title")} onClose={close}>
            {chosen ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  // React events still bubble out of a portal, to the message box's form.
                  e.stopPropagation();
                  onInsert(fill(chosen.body, values));
                  close();
                }}
              >
                <p className="mb-4 whitespace-pre-wrap text-ink-soft" dir="auto">{chosen.body}</p>
                {fields.map((name, i) => (
                  <label key={name} className="mb-3 block font-bold">
                    <span dir="auto">{name}</span>
                    <input
                      className="field mt-1 w-full"
                      dir="auto"
                      autoFocus={i === 0}
                      value={values[name] ?? ""}
                      onChange={(e) => setValues({ ...values, [name]: e.target.value })}
                    />
                  </label>
                ))}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button className="btn btn-pink">{t("templates.use")}</button>
                  <button type="button" className="btn" onClick={() => setChosen(null)}>{t("templates.back")}</button>
                </div>
              </form>
            ) : (
              <>
                <p className="mb-4 text-[14px] text-ink-soft">{t("templates.help")}</p>
                {own && own.length > 0 && (
                  <>
                    <h3 className="eyebrow mb-2">{t("templates.yours")}</h3>
                    <ul className="mb-5 space-y-2">
                      {own.map((row) => (
                        <li key={row.id} className="flex items-stretch gap-2">
                          <button type="button" className="sheet flex-1 p-3 text-start" onClick={() => choose(row)}>
                            <strong className="block" dir="auto">{row.title}</strong>
                            <span className="line-clamp-2 text-[13px] text-ink-soft" dir="auto">{row.body}</span>
                          </button>
                          <button type="button" className="btn" aria-label={t("templates.delete", { name: row.title })} onClick={() => void remove(row.id)}>
                            <Icon name="trash" size={16} />
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                <h3 className="eyebrow mb-2">{t("templates.starters")}</h3>
                <ul className="space-y-2">
                  {starters.map((row) => (
                    <li key={row.title}>
                      <button type="button" className="sheet w-full p-3 text-start" onClick={() => choose(row)}>
                        <strong className="block">{row.title}</strong>
                        <span className="line-clamp-2 text-[13px] text-ink-soft">{row.body}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                {current.trim() && (
                  <form
                    className="mt-6 border-t-2 border-ink/15 pt-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      if (saveTitle.trim()) void saveCurrent();
                    }}
                  >
                    <label htmlFor="template-title" className="block font-bold">{t("templates.saveCurrent")}</label>
                    <p className="mb-2 mt-1 text-[13px] text-ink-soft">{t("templates.saveHelp")}</p>
                    <div className="flex gap-2">
                      <input id="template-title" className="field flex-1" dir="auto" maxLength={80} value={saveTitle} onChange={(e) => setSaveTitle(e.target.value)} placeholder={t("templates.name")} />
                      <button className="btn btn-sun" disabled={!saveTitle.trim()}>{t("common.save")}</button>
                    </div>
                  </form>
                )}
                {note && <p role="status" className="mt-3 font-semibold">{note}</p>}
              </>
            )}
        </Drawer>,
        document.body,
      )}
    </>
  );
}
