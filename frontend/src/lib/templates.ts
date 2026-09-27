/**
 * Starter prompts with {blanks}, for anyone to use or copy into their own.
 * A blank is a word in braces; the picker asks for each one before the text
 * goes into the message box.
 */
export interface Starter {
  id: string;
  agent_id: string | null;
  title: { en: string; ar: string };
  body: { en: string; ar: string };
}

export const STARTERS: Starter[] = [
  {
    id: "plan-week",
    agent_id: null,
    title: { en: "Plan my week", ar: "خطط لأسبوعي" },
    body: {
      en: "Help me plan this week. My priorities are {priorities}, and I have about {hours} free hours.",
      ar: "ساعدني في التخطيط لهذا الأسبوع. أولوياتي هي {الأولويات}، ولدي نحو {الساعات} ساعة فراغ.",
    },
  },
  {
    id: "decide",
    agent_id: null,
    title: { en: "Help me decide", ar: "ساعدني في القرار" },
    body: {
      en: "I'm deciding between {option A} and {option B}. What matters most to me is {what matters}. Walk me through it.",
      ar: "أنا متردد بين {الخيار الأول} و{الخيار الثاني}. أهم شيء عندي هو {ما يهمني}. ساعدني أفكر في الأمر.",
    },
  },
  {
    id: "study-explain",
    agent_id: "study",
    title: { en: "Explain a topic simply", ar: "اشرح موضوعًا ببساطة" },
    body: {
      en: "Explain {topic} as if I'm new to it, then give me three questions to check I understood.",
      ar: "اشرح {الموضوع} كأنني جديد عليه، ثم أعطني ثلاثة أسئلة لأتأكد أنني فهمت.",
    },
  },
  {
    id: "study-plan",
    agent_id: "study",
    title: { en: "Revision plan", ar: "خطة مراجعة" },
    body: {
      en: "My {subject} exam is on {date}. Make me a revision plan with short daily sessions.",
      ar: "امتحان {المادة} يوم {التاريخ}. ضع لي خطة مراجعة بجلسات يومية قصيرة.",
    },
  },
  {
    id: "career-interview",
    agent_id: "career",
    title: { en: "Interview practice", ar: "تدريب على المقابلة" },
    body: {
      en: "I have an interview for {role} at {company}. Ask me the five questions I'm most likely to get, one at a time.",
      ar: "لدي مقابلة لوظيفة {الوظيفة} في {الشركة}. اسألني الأسئلة الخمسة الأكثر احتمالًا، سؤالًا بعد سؤال.",
    },
  },
  {
    id: "career-bullet",
    agent_id: "career",
    title: { en: "Sharpen a CV bullet", ar: "حسّن سطرًا في السيرة" },
    body: {
      en: "Rewrite this CV bullet for a {role} role, with a strong verb and a result: {bullet}",
      ar: "أعد كتابة هذا السطر من سيرتي لوظيفة {الوظيفة}، بفعل قوي ونتيجة واضحة: {السطر}",
    },
  },
  {
    id: "research-compare",
    agent_id: "research",
    title: { en: "Compare two things", ar: "قارن بين شيئين" },
    body: {
      en: "Compare {first} and {second} for {purpose}. Keep it to the differences that matter.",
      ar: "قارن بين {الأول} و{الثاني} من أجل {الغرض}. اكتفِ بالفروق المهمة.",
    },
  },
  {
    id: "writing-tone",
    agent_id: "writing",
    title: { en: "Change the tone", ar: "غيّر الأسلوب" },
    body: {
      en: "Rewrite this to sound {tone}, keeping it about the same length: {text}",
      ar: "أعد كتابة هذا بأسلوب {الأسلوب} مع الحفاظ على طوله تقريبًا: {النص}",
    },
  },
  {
    id: "email-reply",
    agent_id: "email",
    title: { en: "Reply to an email", ar: "رد على بريد" },
    body: {
      en: "Draft a {tone} reply to this email. I want to say {my answer}.\n\n{email}",
      ar: "اكتب ردًا {الأسلوب} على هذا البريد. أريد أن أقول {ردي}.\n\n{البريد}",
    },
  },
  {
    id: "finance-budget",
    agent_id: "finance",
    title: { en: "Monthly budget", ar: "ميزانية شهرية" },
    body: {
      en: "My monthly income is {income} {currency}. Fixed costs are {fixed costs}. Help me split the rest between saving and spending.",
      ar: "دخلي الشهري {الدخل} {العملة}. التكاليف الثابتة {التكاليف}. ساعدني أقسّم الباقي بين الادخار والإنفاق.",
    },
  },
  {
    id: "finance-jameya",
    agent_id: "finance",
    title: { en: "Savings circle (jameya)", ar: "جمعية" },
    body: {
      en: "I'm joining a savings circle of {people} people paying {amount} a month. Which turn should I take if my goal is {goal}?",
      ar: "سأشترك في جمعية من {العدد} أشخاص، القسط {المبلغ} شهريًا. أي دور آخذ إذا كان هدفي {الهدف}؟",
    },
  },
  {
    id: "fitness-routine",
    agent_id: "fitness",
    title: { en: "A routine that fits", ar: "روتين يناسبني" },
    body: {
      en: "Make me a {days}-day weekly routine I can do at {place} in {minutes} minutes a session.",
      ar: "ضع لي روتينًا أسبوعيًا من {الأيام} أيام أستطيع أداءه في {المكان} خلال {الدقائق} دقيقة للجلسة.",
    },
  },
  {
    id: "travel-trip",
    agent_id: "travel",
    title: { en: "Plan a trip", ar: "خطط لرحلة" },
    body: {
      en: "Plan {days} days in {city} for {who}, with a budget of about {budget}.",
      ar: "خطط لـ{الأيام} أيام في {المدينة} لـ{المسافرين}، بميزانية نحو {الميزانية}.",
    },
  },
  {
    id: "shopping-choose",
    agent_id: "shopping",
    title: { en: "Help me choose", ar: "ساعدني أختار" },
    body: {
      en: "I want to buy a {product} for about {budget}. I mostly need it for {use}. What should I look for?",
      ar: "أريد شراء {المنتج} بنحو {الميزانية}. أحتاجه غالبًا لـ{الاستخدام}. ما الذي أبحث عنه؟",
    },
  },
];

/** The blanks in a template, in order, each once. */
export function blanks(body: string): string[] {
  return [...new Set([...body.matchAll(/\{([^{}\n]{1,40})\}/g)].map((m) => m[1]))];
}

export function fill(body: string, values: Record<string, string>): string {
  return body.replace(/\{([^{}\n]{1,40})\}/g, (whole, name: string) => values[name]?.trim() || whole);
}
