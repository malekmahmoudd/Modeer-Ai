import { intlTag, type Locale } from "@/lib/i18n";

/** The currencies of Egypt and the Gulf, then the dollar. */
export const CURRENCIES = ["EGP", "SAR", "AED", "KWD", "QAR", "BHD", "OMR", "USD"] as const;
export type Currency = (typeof CURRENCIES)[number];

/** An amount as it is written where the currency is used: "EGP 1,250.00" in
 *  English, "‏١٬٢٥٠٫٠٠ ج.م.‏" in Arabic. */
export function formatMoney(amount: number, currency: Currency, locale: Locale): string {
  return new Intl.NumberFormat(intlTag(locale) ?? "en", {
    style: "currency",
    currency,
    maximumFractionDigits: amount >= 1000 ? 0 : 2,
  }).format(amount);
}

/** Grams of gold in the nisab, the threshold below which no zakat is due. */
export const NISAB_GOLD_GRAMS = 85;
export const ZAKAT_RATE = 0.025;

export interface ZakatInput {
  cash: number;
  gold: number;
  investments: number;
  owedToYou: number;
  debtsDue: number;
  goldPricePerGram: number;
}

export function zakat(input: ZakatInput) {
  const wealth = Math.max(0, input.cash + input.gold + input.investments + input.owedToYou - input.debtsDue);
  const nisab = input.goldPricePerGram * NISAB_GOLD_GRAMS;
  const due = nisab > 0 && wealth >= nisab ? wealth * ZAKAT_RATE : 0;
  return { wealth, nisab, due };
}

/** A savings circle (جمعية): everyone pays each month; one member a month
 *  takes the whole pot, in turn. */
export function circle(members: number, monthly: number, turn: number) {
  const pot = members * monthly;
  const paidBefore = turn * monthly; // including the month you receive
  return {
    pot,
    totalPaid: pot,
    /** How much of the pot arrives before you have paid it in: an interest-free
     *  loan from the others. Zero for the last turn, which is pure saving. */
    advance: pot - paidBefore,
    turn,
  };
}
