"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/ui/primitives";
import { intlTag, usePrefs } from "@/lib/i18n";
import { circle, CURRENCIES, formatMoney, NISAB_GOLD_GRAMS, zakat, type Currency } from "@/lib/money";

const CURRENCY_KEY = "fareeq.currency";

function readCurrency(): Currency {
  try {
    const saved = localStorage.getItem(CURRENCY_KEY);
    return (CURRENCIES as readonly string[]).includes(saved ?? "") ? (saved as Currency) : "EGP";
  } catch {
    return "EGP";
  }
}

/** A count in the page's language (rendered the same on the server and here). */
function useCount() {
  const { locale } = usePrefs();
  return (n: number) => new Intl.NumberFormat(intlTag(locale)).format(n);
}

/** Arabic-Indic digits typed into a number box become numbers too. */
function num(value: string): number {
  const western = value.replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d))).replace(/[٬,]/g, "").replace("٫", ".");
  const n = Number(western);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

/** Zakat and savings-circle calculators, in the person's currency. Education
 *  only: no live prices, and a scholar settles the details of zakat. */
export function MoneyTools() {
  const { t, locale } = usePrefs();
  const [currency, setCurrency] = useState<Currency>("EGP");
  useEffect(() => setCurrency(readCurrency()), []);
  const money = (n: number) => formatMoney(n, currency, locale);

  return (
    <div className="anim-fade max-w-3xl">
      <PageHeader eyebrow={t("money.eyebrow")} title={t("money.title")} lede={t("money.lede")} />
      <label className="mb-6 flex flex-wrap items-center gap-3 font-bold">
        {t("money.currency")}
        <select className="field !w-auto" value={currency} onChange={(e) => {
          const next = e.target.value as Currency;
          setCurrency(next);
          try {
            localStorage.setItem(CURRENCY_KEY, next);
          } catch {
            /* remembered for this visit only */
          }
        }}>
          {CURRENCIES.map((c) => <option key={c} value={c}>{t(`money.cur.${c}`)} ({c})</option>)}
        </select>
      </label>
      <Zakat money={money} />
      <Circle money={money} />
      <p className="mt-6 text-[14px] text-ink-soft">
        {t("money.askEmma")} <Link href="/agents/finance" className="font-bold underline decoration-pink decoration-2 underline-offset-4">{t("money.emma")}</Link>
      </p>
    </div>
  );
}

function Amount({ label, value, onChange, help }: { label: string; value: string; onChange: (v: string) => void; help?: string }) {
  return (
    <label className="block text-[14px] font-bold">
      {label}
      <input className="field mt-1 w-full" inputMode="decimal" dir="ltr" value={value} onChange={(e) => onChange(e.target.value)} />
      {help && <span className="mt-1 block text-[12.5px] font-semibold text-ink-soft">{help}</span>}
    </label>
  );
}

function Zakat({ money }: { money: (n: number) => string }) {
  const { t } = usePrefs();
  const formatNumber = useCount();
  const [v, setV] = useState({ cash: "", gold: "", investments: "", owedToYou: "", debtsDue: "", goldPricePerGram: "" });
  const set = (key: keyof typeof v) => (value: string) => setV({ ...v, [key]: value });
  const result = zakat({
    cash: num(v.cash),
    gold: num(v.gold),
    investments: num(v.investments),
    owedToYou: num(v.owedToYou),
    debtsDue: num(v.debtsDue),
    goldPricePerGram: num(v.goldPricePerGram),
  });
  return (
    <section className="mb-8 border-2 border-ink bg-paper-hi p-5 shadow-pop-xs" aria-labelledby="zakat-title">
      <h2 id="zakat-title" className="display text-2xl">{t("money.zakat")}</h2>
      <p className="my-3 text-ink-soft">{t("money.zakatHelp")}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Amount label={t("money.cash")} value={v.cash} onChange={set("cash")} />
        <Amount label={t("money.gold")} value={v.gold} onChange={set("gold")} />
        <Amount label={t("money.investments")} value={v.investments} onChange={set("investments")} />
        <Amount label={t("money.owed")} value={v.owedToYou} onChange={set("owedToYou")} />
        <Amount label={t("money.debts")} value={v.debtsDue} onChange={set("debtsDue")} />
        <Amount label={t("money.goldPrice")} value={v.goldPricePerGram} onChange={set("goldPricePerGram")} help={t("money.goldPriceHelp")} />
      </div>
      <div role="status" className="mt-4 border-2 border-ink bg-sun-pale p-4">
        {result.nisab === 0 ? (
          <p className="font-semibold">{t("money.needPrice")}</p>
        ) : (
          <>
            <p>{t("money.nisab", { grams: formatNumber(NISAB_GOLD_GRAMS), amount: money(result.nisab) })}</p>
            <p>{t("money.wealth", { amount: money(result.wealth) })}</p>
            <p className="mt-2 text-[18px] font-black">
              {result.due > 0 ? t("money.due", { amount: money(result.due) }) : t("money.notDue")}
            </p>
          </>
        )}
      </div>
      <p className="mt-3 text-[13px] text-ink-soft">{t("money.zakatNote")}</p>
    </section>
  );
}

function Circle({ money }: { money: (n: number) => string }) {
  const { t } = usePrefs();
  const formatNumber = useCount();
  const [members, setMembers] = useState("10");
  const [monthly, setMonthly] = useState("");
  const [turn, setTurn] = useState("1");
  const n = Math.min(60, Math.max(2, Math.round(num(members)) || 2));
  const k = Math.min(n, Math.max(1, Math.round(num(turn)) || 1));
  const amount = num(monthly);
  const result = circle(n, amount, k);
  return (
    <section className="border-2 border-ink bg-paper-hi p-5 shadow-pop-xs" aria-labelledby="circle-title">
      <h2 id="circle-title" className="display text-2xl">{t("money.circle")}</h2>
      <p className="my-3 text-ink-soft">{t("money.circleHelp")}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <Amount label={t("money.members")} value={members} onChange={setMembers} />
        <Amount label={t("money.monthly")} value={monthly} onChange={setMonthly} />
        <Amount label={t("money.turn")} value={turn} onChange={setTurn} help={t("money.turnHelp", { n: formatNumber(n) })} />
      </div>
      {amount > 0 && (
        <div role="status" className="mt-4 border-2 border-ink bg-sun-pale p-4">
          <p>{t("money.pot", { amount: money(result.pot), month: formatNumber(k) })}</p>
          <p>{t("money.totalPaid", { amount: money(result.totalPaid), months: formatNumber(n) })}</p>
          <p className="mt-2 font-bold">
            {result.advance > 0 ? t("money.early", { amount: money(result.advance) }) : t("money.last")}
          </p>
        </div>
      )}
      <p className="mt-3 text-[13px] text-ink-soft">{t("money.circleRisk")}</p>
    </section>
  );
}
