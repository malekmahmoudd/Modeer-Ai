"use client";

import { useCallback } from "react";

import { usePrefs } from "@/lib/i18n";
import type { Agent } from "@/types";

/**
 * The agents' own words on screen — name, role, tagline, the prompt in an empty
 * chat and the starter suggestions — in Arabic. The server sends English; in
 * English the server's text is shown as it is. A starter is sent as a message,
 * so an Arabic starter gets an Arabic answer.
 */
interface AgentText {
  name: string;
  role: string;
  tagline: string;
  placeholder: string;
  empty: string;
  starters: string[];
}

const ARABIC: Record<string, AgentText> = {
  modeer: {
    name: "ليو",
    role: "المساعد الشخصي وحافظ السياق",
    tagline: "يعرفك، ويُبقي الفريق على اطلاع",
    placeholder: "بماذا تفكر؟",
    empty: "بماذا تفكر؟",
    starters: ["ساعدني في تحديد أهدافي", "على ماذا أركّز هذا الأسبوع؟", "هذا شيء عني يجب أن تعرفه", "أعطني ملخص اليوم"],
  },
  study: {
    name: "نوفا",
    role: "مدربة التعلّم والشرح",
    tagline: "تعلّم، استعد، افهم",
    placeholder: "ماذا تتعلم؟",
    empty: "ماذا تريد أن تتعلم أو تراجع؟",
    starters: ["اشرح لي موضوعًا عالقًا فيه", "ضع لي خطة مذاكرة", "اختبرني في مادة", "ساعدني في الاستعداد لامتحان"],
  },
  career: {
    name: "هارفي",
    role: "استراتيجي ومدرب مهني",
    tagline: "وظائف، سير ذاتية، مقابلات",
    placeholder: "اسأل عن مسارك المهني…",
    empty: "على ماذا تعمل؟",
    starters: ["راجع سيرتي الذاتية", "جهّزني لمقابلة", "ساعدني في الاختيار بين وظيفتين", "ضع لي خطة مهنية"],
  },
  research: {
    name: "كلارا",
    role: "محللة أبحاث",
    tagline: "حلّل وتقصَّ",
    placeholder: "ماذا تريد أن تبحث؟",
    empty: "ما السؤال الذي تحاول الإجابة عنه؟",
    starters: ["ساعدني في تحديد سؤال بحثي", "وازن الأدلة حول موضوع", "نظّم لي خطة تقصٍّ", "لخّص الحجج مع وضد"],
  },
  writing: {
    name: "أليكس",
    role: "شريك الكتابة والمحرر",
    tagline: "اكتب، حرّر، هذّب",
    placeholder: "ماذا تكتب؟",
    empty: "ماذا تكتب، ولمن؟",
    starters: ["حرّر لي فقرة", "ساعدني في وضع مخطط لنص", "أعد الصياغة بأسلوبي", "اختصر هذا دون أن تفقد صوتي"],
  },
  travel: {
    name: "تيسا",
    role: "مخططة الرحلات",
    tagline: "رحلات تناسبك",
    placeholder: "إلى أين تفكر في الذهاب؟",
    empty: "ما الرحلة التي تخطط لها؟",
    starters: ["خطّط لرحلة أسبوع", "اقترح عطلة نهاية أسبوع طويلة", "قسّم ميزانية رحلة", "ساعدني في اختيار وجهة"],
  },
  shopping: {
    name: "نيت",
    role: "مستشار الشراء",
    tagline: "قارن، قرّر، اشترِ بذكاء",
    placeholder: "ماذا تحاول أن تشتري؟",
    empty: "ماذا تحاول أن تشتري؟",
    starters: ["ساعدني في الاختيار بين خيارين", "حوّل احتياجي إلى معايير شراء", "هل يستحق سعره؟", "ما الفئة المناسبة لاستخدامي؟"],
  },
  finance: {
    name: "إيما",
    role: "دليل المال الشخصي (تثقيفي)",
    tagline: "ميزانيات، مفاضلات، تخطيط",
    placeholder: "ما القرار المالي الذي تفكر فيه؟",
    empty: "ماذا تحاول أن تحسم؟",
    starters: ["كم يجب أن يكون صندوق الطوارئ؟", "سداد الدين أم الادخار — كيف أفكر؟", "ساعدني في تحديد هدف ادخار", "اشرح لي كيف يعمل هذا المنتج المالي"],
  },
  fitness: {
    name: "مادي",
    role: "مدربة التمارين والعادات (غير طبية)",
    tagline: "تمرّن بخطة حقيقية",
    placeholder: "ما هدفك من التمرين؟",
    empty: "لماذا تتمرن؟",
    starters: ["ضع لي خطة تمارين أسبوعية", "عدّل روتيني لأسبوع مزدحم", "كيف أحافظ على عادة؟", "تمرّن مع مراعاة قيد لديّ"],
  },
  email: {
    name: "نورا",
    role: "مدربة كتابة البريد والمراسلات",
    tagline: "بريد يصل إلى هدفه",
    placeholder: "ماذا تحتاج أن ترسل؟",
    empty: "ما البريد الذي تحتاج أن تكتبه؟",
    starters: ["اكتب لي ردًا", "اجعل هذه الرسالة أحزم بلطف", "ساعدني في الرفض بأدب", "ذكّر شخصًا لم يرد دون إلحاح"],
  },
};

/** "Nova" from "Nova" or "Study Agent". */
export function shortName(name: string): string {
  return name.replace(/ (Agent|Assistant)$/, "");
}

export function agentText(agent: Pick<Agent, "id" | "name" | "role" | "tagline" | "composer_placeholder" | "empty_prompt" | "starters">, locale: string): AgentText {
  const arabic = locale === "ar" ? ARABIC[agent.id] : undefined;
  return (
    arabic ?? {
      name: shortName(agent.name),
      role: agent.role,
      tagline: agent.tagline,
      placeholder: agent.composer_placeholder,
      empty: agent.empty_prompt,
      starters: agent.starters,
    }
  );
}

/** An agent's short display name, in the interface language. */
export function useAgentName() {
  const { locale } = usePrefs();
  return useCallback(
    (agent: { id: string; name: string } | undefined, fallback = "") =>
      agent ? (locale === "ar" && ARABIC[agent.id] ? ARABIC[agent.id].name : shortName(agent.name)) : fallback,
    [locale],
  );
}

export function useAgentText() {
  const { locale } = usePrefs();
  return useCallback((agent: Agent) => agentText(agent, locale), [locale]);
}
