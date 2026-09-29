"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ACCOUNT_KEY, draftKey, readDraft, writeDraft } from "@/lib/drafts";
import { Icon } from "@/components/ui/Icon";
import { EmptyState, ErrorNote, PageHeader, Spinner } from "@/components/ui/primitives";
import { API_BASE, apiFetch, useApi } from "@/lib/api";
import { checkBullet, EMPTY_ROLE, EMPTY_STUDY, splitList, type BulletIssue, type Cv, type CvData, type Role, type Study } from "@/lib/cv";
import { usePrefs } from "@/lib/i18n";
import type { MessageKey } from "@/lib/i18n/en";

/** The form keeps lists as typed text ("SQL, Roadmaps"; one bullet per line),
 *  so commas and new lines can be typed freely; they become lists on save. */
interface Draft {
  title: string;
  target_role: string;
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  links: string;
  summary: string;
  experience: (Omit<Role, "bullets"> & { bullets: string })[];
  education: Study[];
  skills: string;
  languages: string;
}

function toDraft(cv: Cv): Draft {
  const d = cv.data;
  return {
    title: cv.title,
    target_role: cv.target_role ?? "",
    name: d.name,
    headline: d.headline,
    email: d.email,
    phone: d.phone,
    location: d.location,
    links: d.links.join(", "),
    summary: d.summary,
    experience: d.experience.map((r) => ({ ...r, bullets: r.bullets.join("\n") })),
    education: d.education,
    skills: d.skills.join(", "),
    languages: d.languages.join(", "),
  };
}

function toData(d: Draft): CvData {
  return {
    name: d.name,
    headline: d.headline,
    email: d.email,
    phone: d.phone,
    location: d.location,
    links: splitList(d.links, 4),
    summary: d.summary,
    experience: d.experience.map((r) => ({ ...r, bullets: r.bullets.split("\n").map((b) => b.trim()).filter(Boolean).slice(0, 8) })),
    education: d.education,
    skills: splitList(d.skills, 40),
    languages: splitList(d.languages, 10),
  };
}

/** Structured CVs, one version per role, with bullet checks, a Word file and
 *  a print layout for PDF. */
export function CvBuilder() {
  const { t } = usePrefs();
  const { data: account, error: accountError, refetch: reloadAccount } = useApi<{ id: string }>("/users/me");
  const { data: cvs, loading, setData: setCvs } = useApi<Cv[]>("/cv");
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const current = cvs?.find((c) => c.id === currentId) ?? cvs?.[0] ?? null;
  const storageKey = account && current ? draftKey(account.id, "cv", current.id) : null;
  // Load the chosen version into the form when the choice changes.
  const [loadedId, setLoadedId] = useState<string | null>(null);
  if (current && storageKey && storageKey !== loadedId) {
    setLoadedId(storageKey);
    setCurrentId(current.id);
    let restored: Draft | null = null;
    try {
      const value = JSON.parse(readDraft(storageKey) || "null");
      const base = toDraft(current);
      if (value && Object.keys(base).every((key) =>
        Array.isArray(base[key as keyof Draft]) ? Array.isArray(value[key]) : typeof value[key] === "string")) {
        restored = value;
      }
    } catch { /* Ignore an unreadable local draft. */ }
    setDraft(restored ?? toDraft(current));
    setDirty(!!restored);
    if (restored) setNotice(t("cv.recovered"));
  }

  // Counts edits, so a save that finishes after more typing does not mark
  // the newer text as saved.
  const edits = useRef(0);
  const working = useRef(false);

  // Warn on reload/close as a fallback when browser storage is unavailable.
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      // Never let a discard prompt obstruct sign-out or another tab's account switch.
      try { if (localStorage.getItem(ACCOUNT_KEY) !== account?.id) return; } catch { /* Warn if storage is blocked. */ }
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, account?.id]);

  async function run(label: string, work: () => Promise<void>) {
    if (working.current) return; // one action at a time
    working.current = true;
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.failed"));
    } finally {
      working.current = false;
      setBusy("");
    }
  }

  function edit(patch: Partial<Draft>) {
    if (!draft) return;
    edits.current += 1;
    const next = { ...draft, ...patch };
    if (storageKey) writeDraft(storageKey, JSON.stringify(next));
    setDraft(next);
    setDirty(true);
  }

  /** Saves the form; throws if the server refuses, leaving the edits in place. */
  async function persist(): Promise<Cv> {
    if (!draft || !current) throw new Error(t("common.failed"));
    const version = edits.current;
    const saved = await apiFetch<Cv>(`/cv/${current.id}`, {
      method: "PUT",
      body: JSON.stringify({ title: draft.title || t("cv.untitled"), target_role: draft.target_role || null, data: toData(draft) }),
    });
    setCvs((list) => (list ?? []).map((c) => (c.id === saved.id ? saved : c)));
    if (edits.current === version) {
      setDirty(false);
      if (storageKey) writeDraft(storageKey, "");
    }
    return saved;
  }

  const save = () =>
    run("save", async () => {
      await persist();
      setNotice(t("cv.saved"));
    });

  const create = () =>
    run("create", async () => {
      const made = await apiFetch<Cv>("/cv", { method: "POST", body: JSON.stringify({ title: t("cv.firstTitle") }) });
      setCvs((list) => [made, ...(list ?? [])]);
      setCurrentId(made.id);
      setDraft(toDraft(made));
      setDirty(false);
    });

  const copy = () =>
    run("copy", async () => {
      if (!current) return;
      const role = window.prompt(t("cv.copyPrompt"));
      if (!role?.trim()) return;
      // The copy starts from what is saved, so unsaved edits are saved first.
      // If that fails, persist() throws: no copy is made and the edits stay.
      if (dirty) await persist();
      const made = await apiFetch<Cv>(`/cv/${current.id}/copy`, {
        method: "POST",
        body: JSON.stringify({ title: role.trim(), target_role: role.trim() }),
      });
      setCvs((list) => [made, ...(list ?? [])]);
      setCurrentId(made.id);
      setDraft(toDraft(made));
      setDirty(false);
      setNotice(t("cv.copied"));
    });

  const remove = () =>
    run("delete", async () => {
      if (!current || !window.confirm(t("cv.deleteConfirm", { title: current.title }))) return;
      await apiFetch(`/cv/${current.id}`, { method: "DELETE" });
      if (storageKey) writeDraft(storageKey, "");
      const rest = (cvs ?? []).filter((c) => c.id !== current.id);
      setCvs(rest);
      setCurrentId(rest[0]?.id ?? null);
      setDraft(rest[0] ? toDraft(rest[0]) : null);
      setDirty(false);
    });

  if (!account && accountError) return <div><ErrorNote message={accountError} /><button className="btn mt-3" onClick={() => void reloadAccount()}>{t("common.tryAgain")}</button></div>;
  if (!account || (loading && !cvs)) return <Spinner />;

  return (
    <div className="anim-fade">
      <div className="print:hidden">
        <PageHeader
          eyebrow={t("cv.eyebrow")}
          title={t("cv.title")}
          lede={t("cv.lede")}
          action={<button className="btn btn-sun" disabled={!!busy} onClick={create}><Icon name="plus" size={16} /> {t("cv.new")}</button>}
        />
        {error && <div className="mb-4"><ErrorNote message={error} /></div>}
        {notice && <p role="status" className="mb-4 border-2 border-ink bg-sun-pale p-3 font-semibold">{notice}</p>}
      </div>
      {!current || !draft ? (
        <EmptyState title={t("cv.empty")} action={<button className="btn btn-pink" disabled={!!busy} onClick={create}>{t("cv.start")}</button>}>
          {t("cv.emptyHelp")}
        </EmptyState>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="space-y-5 print:hidden">
            <div className="flex flex-wrap items-end gap-2 border-2 border-ink bg-paper-hi p-3">
              <label className="block min-w-[12rem] flex-1 font-bold">
                {t("cv.version")}
                <select className="field mt-1 w-full" value={current.id} onChange={(e) => {
                  if (dirty && !window.confirm(t("cv.discard"))) return;
                  if (storageKey) writeDraft(storageKey, "");
                  setCurrentId(e.target.value);
                  const next = cvs?.find((c) => c.id === e.target.value);
                  if (next) setDraft(toDraft(next));
                  setDirty(false);
                }}>
                  {cvs?.map((c) => <option key={c.id} value={c.id}>{c.title}{c.target_role ? ` · ${c.target_role}` : ""}</option>)}
                </select>
              </label>
              <button className="btn" disabled={!!busy} onClick={copy}>{t("cv.copy")}</button>
              <button className="btn" disabled={!!busy} onClick={remove} aria-label={t("cv.delete")}><Icon name="trash" size={16} /></button>
            </div>

            <Fieldset legend={t("cv.about")}>
              <Grid>
                <Field label={t("cv.versionName")} value={draft.title} onChange={(title) => edit({ title })} max={120} />
                <Field label={t("cv.targetRole")} value={draft.target_role} onChange={(target_role) => edit({ target_role })} max={120} />
                <Field label={t("cv.name")} value={draft.name} onChange={(name) => edit({ name })} max={120} />
                <Field label={t("cv.headline")} value={draft.headline} onChange={(headline) => edit({ headline })} max={120} />
                <Field label={t("common.email")} value={draft.email} onChange={(email) => edit({ email })} max={120} type="email" />
                <Field label={t("cv.phone")} value={draft.phone} onChange={(phone) => edit({ phone })} max={40} type="tel" />
                <Field label={t("cv.location")} value={draft.location} onChange={(location) => edit({ location })} max={120} />
                <Field label={t("cv.links")} value={draft.links} onChange={(links) => edit({ links })} />
              </Grid>
              <Area label={t("cv.summary")} value={draft.summary} onChange={(summary) => edit({ summary })} max={1200} rows={4} />
            </Fieldset>

            <Fieldset legend={t("cv.experience")}>
              {draft.experience.map((role, i) => (
                <div key={i} className="mb-4 border-2 border-ink/25 p-3">
                  <Grid>
                    <Field label={t("cv.jobTitle")} value={role.title} onChange={(title) => edit({ experience: replace(draft.experience, i, { ...role, title }) })} max={120} />
                    <Field label={t("cv.organisation")} value={role.organisation} onChange={(organisation) => edit({ experience: replace(draft.experience, i, { ...role, organisation }) })} max={120} />
                    <Field label={t("cv.from")} value={role.start} onChange={(start) => edit({ experience: replace(draft.experience, i, { ...role, start }) })} max={30} />
                    <Field label={t("cv.to")} value={role.end} onChange={(end) => edit({ experience: replace(draft.experience, i, { ...role, end }) })} max={30} />
                  </Grid>
                  <Area label={t("cv.bullets")} value={role.bullets} onChange={(bullets) => edit({ experience: replace(draft.experience, i, { ...role, bullets }) })} rows={5} />
                  <BulletChecks bullets={role.bullets} />
                  <button className="btn mt-2" onClick={() => edit({ experience: draft.experience.filter((_, j) => j !== i) })}>{t("cv.removeRole")}</button>
                </div>
              ))}
              {draft.experience.length < 12 && (
                <button className="btn" onClick={() => edit({ experience: [...draft.experience, { ...EMPTY_ROLE, bullets: "" }] })}><Icon name="plus" size={16} /> {t("cv.addRole")}</button>
              )}
            </Fieldset>

            <Fieldset legend={t("cv.education")}>
              {draft.education.map((study, i) => (
                <div key={i} className="mb-4 border-2 border-ink/25 p-3">
                  <Grid>
                    <Field label={t("cv.qualification")} value={study.qualification} onChange={(qualification) => edit({ education: replace(draft.education, i, { ...study, qualification }) })} max={120} />
                    <Field label={t("cv.institution")} value={study.institution} onChange={(institution) => edit({ education: replace(draft.education, i, { ...study, institution }) })} max={120} />
                    <Field label={t("cv.from")} value={study.start} onChange={(start) => edit({ education: replace(draft.education, i, { ...study, start }) })} max={30} />
                    <Field label={t("cv.to")} value={study.end} onChange={(end) => edit({ education: replace(draft.education, i, { ...study, end }) })} max={30} />
                  </Grid>
                  <button className="btn mt-2" onClick={() => edit({ education: draft.education.filter((_, j) => j !== i) })}>{t("cv.removeStudy")}</button>
                </div>
              ))}
              {draft.education.length < 6 && (
                <button className="btn" onClick={() => edit({ education: [...draft.education, { ...EMPTY_STUDY }] })}><Icon name="plus" size={16} /> {t("cv.addStudy")}</button>
              )}
            </Fieldset>

            <Fieldset legend={t("cv.skillsAndLanguages")}>
              <Area label={t("cv.skills")} value={draft.skills} onChange={(skills) => edit({ skills })} rows={2} />
              <Field label={t("cv.languages")} value={draft.languages} onChange={(languages) => edit({ languages })} />
            </Fieldset>

            <div className="sticky bottom-20 z-10 flex flex-wrap gap-2 border-2 border-ink bg-paper p-3 shadow-pop-xs md:bottom-4">
              <button className="btn btn-pink" disabled={!!busy || !dirty} onClick={save}>{busy === "save" ? t("common.saving") : dirty ? t("common.save") : t("cv.allSaved")}</button>
              <a
                className={`btn ${dirty ? "pointer-events-none opacity-50" : ""}`}
                aria-disabled={dirty}
                href={`${API_BASE}/cv/${current.id}/docx`}
                title={dirty ? t("cv.saveFirst") : undefined}
              >
                <Icon name="download" size={16} /> {t("cv.word")}
              </a>
              <button className="btn" onClick={() => window.print()}>{t("cv.pdf")}</button>
              <Link href="/agents/career" className="btn">{t("cv.askHarvey")}</Link>
            </div>
          </div>
          <CvPreview data={toData(draft)} />
        </div>
      )}
    </div>
  );
}

function replace<T>(list: T[], index: number, value: T): T[] {
  return list.map((item, i) => (i === index ? value : item));
}

function Fieldset({ legend, children }: { legend: string; children: React.ReactNode }) {
  return (
    <fieldset className="border-2 border-ink bg-paper-hi p-4">
      <legend className="display px-1 text-[18px]">{legend}</legend>
      <div className="space-y-3">{children}</div>
    </fieldset>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2">{children}</div>;
}

function Field({ label, value, onChange, max, type = "text" }: { label: string; value: string; onChange: (v: string) => void; max?: number; type?: string }) {
  return (
    <label className="block text-[14px] font-bold">
      {label}
      <input className="field mt-1 w-full" dir="auto" type={type} maxLength={max} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function Area({ label, value, onChange, max, rows }: { label: string; value: string; onChange: (v: string) => void; max?: number; rows: number }) {
  return (
    <label className="block text-[14px] font-bold">
      {label}
      <textarea className="field mt-1 w-full" dir="auto" rows={rows} maxLength={max} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

/** One line of advice per bullet that could be stronger. */
function BulletChecks({ bullets }: { bullets: string }) {
  const { t } = usePrefs();
  const lines = bullets.split("\n").map((b) => b.trim()).filter(Boolean);
  const notes: { line: number; issue: BulletIssue | "many" }[] = lines.flatMap((line, i) =>
    checkBullet(line).map((issue) => ({ line: i + 1, issue })),
  );
  if (lines.length > 8) notes.unshift({ line: 9, issue: "many" });
  if (!notes.length) return lines.length ? <p className="mt-1 text-[13px] font-semibold text-ink-soft">✓ {t("cv.bulletsGood")}</p> : null;
  return (
    <ul className="mt-1 space-y-0.5 text-[13px] text-ink-soft" aria-label={t("cv.checks")}>
      {notes.map(({ line, issue }, i) => (
        <li key={i}>{t(`cv.check.${issue}` as MessageKey, { n: line })}</li>
      ))}
    </ul>
  );
}

/** How the CV reads; also what is printed (Save as PDF). */
function CvPreview({ data }: { data: CvData }) {
  const { t } = usePrefs();
  const contact = [data.email, data.phone, data.location, ...data.links].filter(Boolean).join(" · ");
  return (
    <article className="cv-print self-start border-2 border-ink bg-white p-6 text-[14px] leading-relaxed text-black shadow-pop-xs print:border-0 print:p-0 print:shadow-none lg:sticky lg:top-24" dir="auto" aria-label={t("cv.preview")}>
      <h2 className="text-[26px] font-black">{data.name || t("cv.name")}</h2>
      {data.headline && <p className="text-[16px] text-neutral-700">{data.headline}</p>}
      {contact && <p className="mt-1 text-[12.5px]">{contact}</p>}
      {data.summary && <Section title={t("cv.summary")}><p>{data.summary}</p></Section>}
      {data.experience.length > 0 && (
        <Section title={t("cv.experience")}>
          {data.experience.map((r, i) => (
            <div key={i} className="mb-3">
              <p className="font-bold">{[r.title, r.organisation, r.place].filter(Boolean).join(" · ")}</p>
              {(r.start || r.end) && <p className="text-[12.5px] text-neutral-600">{[r.start, r.end].filter(Boolean).join(" – ")}</p>}
              <ul className="ms-5 list-disc">{r.bullets.map((b, j) => <li key={j}>{b}</li>)}</ul>
            </div>
          ))}
        </Section>
      )}
      {data.education.length > 0 && (
        <Section title={t("cv.education")}>
          {data.education.map((s, i) => (
            <div key={i} className="mb-2">
              <p className="font-bold">{[s.qualification, s.institution].filter(Boolean).join(" · ")}</p>
              {(s.start || s.end) && <p className="text-[12.5px] text-neutral-600">{[s.start, s.end].filter(Boolean).join(" – ")}</p>}
            </div>
          ))}
        </Section>
      )}
      {data.skills.length > 0 && <Section title={t("cv.skills")}><p>{data.skills.join(", ")}</p></Section>}
      {data.languages.length > 0 && <Section title={t("cv.languages")}><p>{data.languages.join(", ")}</p></Section>}
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-4">
      <h3 className="mb-1 border-b border-neutral-400 text-[13px] font-black uppercase tracking-wide text-[#1f3a5f]">{title}</h3>
      {children}
    </section>
  );
}
