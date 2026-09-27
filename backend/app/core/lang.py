# ruff: noqa: E501 (a catalog of sentences, one per line)
"""Text the server writes, in the person's language.

The interface is translated in the browser (frontend/src/lib/i18n). What comes
from here — error messages, reply notices, the daily briefing and the weekly
summary — is written in English and, for someone using Arabic, put into Arabic
on the way out. What the AI teammates are told stays English: they answer in
whatever language the person writes in.

The language is the account's choice, else the language cookie the browser
sends with every request, else the browser's own preference. Error messages
are translated before the account is loaded, so they go by the cookie; the app
writes the account's choice into that cookie, so the two agree.
"""

from __future__ import annotations

import re
from datetime import date

from fastapi import Request

LOCALE_COOKIE = "fareeq_locale"

ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_WEEKDAYS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")
_MONTHS = (
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
)  # fmt: skip


def request_locale(request: Request | None, user=None) -> str:
    """"ar" or "en" for this request."""
    chosen = getattr(user, "locale", None)
    if chosen in ("ar", "en"):
        return chosen
    if request is None:
        return "en"
    cookie = request.cookies.get(LOCALE_COOKIE)
    if cookie in ("ar", "en"):
        return cookie
    accepted = (request.headers.get("accept-language") or "").strip().lower()
    return "ar" if accepted.startswith("ar") else "en"


def num(value: int | float) -> str:
    """A number in Arabic-Indic digits, as the Arabic interface writes them."""
    text = f"{value:,.0f}" if float(value) == int(value) else f"{value:,.2f}"
    return text.replace(",", "٬").replace(".", "٫").translate(ARABIC_DIGITS)


def day(d: date) -> str:
    """الخميس ١ أكتوبر"""
    return f"{_WEEKDAYS[d.weekday()]} {num(d.day)} {_MONTHS[d.month - 1]}"


def days_phrase(n: int) -> str:
    """Arabic counts agree with the number: يوم، يومان، ٣ أيام، ١١ يومًا."""
    if n == 1:
        return "يوم واحد"
    if n == 2:
        return "يومان"
    if 3 <= n <= 10:
        return f"{num(n)} أيام"
    return f"{num(n)} يومًا" if 11 <= n <= 99 else f"{num(n)} يوم"


def countdown(due: date, today: date) -> str:
    n = (due - today).days
    if n == 0:
        return f"اليوم ({day(due)})"
    if n == 1:
        return f"غدًا ({day(due)})"
    if n < 0:
        return f"{day(due)}، منذ {days_phrase(-n)}"
    return f"{day(due)} (بعد {days_phrase(n)})"


def when_line(row, today: date) -> str:
    """The Arabic of tracking.service.when_line: a day, or a trip's span."""
    ends = getattr(row, "ends_on", None)
    if not ends or ends == row.due_on:
        return countdown(row.due_on, today)
    span = f"من {day(row.due_on)} إلى {day(ends)}"
    if today < row.due_on:
        n = (row.due_on - today).days
        return f"{span} ({'غدًا' if n == 1 else f'بعد {days_phrase(n)}'})"
    if today <= ends:
        return f"{span} (يجري الآن)"
    return f"{span}، انتهت منذ {days_phrase((today - ends).days)}"


# --- messages ---------------------------------------------------------------------------

#: Every fixed message a person can see, in Arabic.
_ARABIC: dict[str, str] = {
    # signing in and the account
    "Please sign in": "سجّل الدخول من فضلك",
    "Request origin is not allowed": "مصدر الطلب غير مسموح به",
    "Too many attempts. Please wait a few minutes and try again.": "محاولات كثيرة. انتظر بضع دقائق ثم حاول مرة أخرى.",
    "Invalid access key": "مفتاح الدخول غير صحيح",
    "That email and password don't match an account.": "البريد وكلمة المرور لا يطابقان أي حساب.",
    "That email and recovery code don't match an account.": "البريد ورمز الاسترداد لا يطابقان أي حساب.",
    "That code isn't right. Check your authenticator app.": "الرمز غير صحيح. تحقّق من تطبيق المصادقة.",
    "That code isn't right. Check the time on your phone, and try the newest code.": "الرمز غير صحيح. تحقّق من الوقت على هاتفك وجرّب أحدث رمز.",
    "That code isn't right.": "الرمز غير صحيح.",
    "Signup is not available": "إنشاء الحسابات غير متاح",
    "An account with that email already exists. Sign in, or use a recovery code.": "يوجد حساب بهذا البريد. سجّل الدخول أو استخدم رمز استرداد.",
    "An account with that email already exists.": "يوجد حساب بهذا البريد.",
    "Your current password is not right.": "كلمة مرورك الحالية غير صحيحة.",
    "Add an email address to this account before setting a password.": "أضف بريدًا إلكترونيًا إلى هذا الحساب قبل تعيين كلمة مرور.",
    "Set a password first; recovery codes recover a password.": "عيّن كلمة مرور أولًا؛ رموز الاسترداد تستعيد كلمة المرور.",
    "That password is not right.": "كلمة المرور غير صحيحة.",
    "That device is not signed in": "هذا الجهاز غير مسجّل الدخول",
    "Set a password first: its recovery codes are your way back in if you lose your phone.": "عيّن كلمة مرور أولًا: رموز الاسترداد الخاصة بها طريق عودتك إن فقدت هاتفك.",
    "Two-step sign-in is already on.": "الدخول بخطوتين مفعّل بالفعل.",
    "Start the setup again.": "ابدأ الإعداد من جديد.",
    "Sign in with an email and password, or with an access key": "سجّل الدخول ببريد وكلمة مرور، أو بمفتاح دخول",
    "Tell us what to call you": "أخبرنا بماذا نناديك",
    "A password cannot be only spaces.": "لا يمكن أن تكون كلمة المرور مسافات فقط.",
    "This account is suspended. Contact whoever runs this service.": "هذا الحساب موقوف. تواصل مع من يدير هذه الخدمة.",
    "That email is already in use.": "هذا البريد مستخدم بالفعل.",
    "Send confirm: DELETE to erase the account": "أرسل التأكيد DELETE لحذف الحساب",
    "This account signs in with its email; it cannot be changed here.": "هذا الحساب يدخل ببريده؛ لا يمكن تغييره من هنا.",
    "Unknown timezone; use an IANA name such as Europe/London": "منطقة زمنية غير معروفة؛ استخدم اسمًا مثل Africa/Cairo",
    "Choose distinct specialists": "اختر متخصصين مختلفين",
    "Profile field names must be 1-40 characters": "يجب أن تكون أسماء حقول الملف من ١ إلى ٤٠ حرفًا",
    "must not be null": "لا يمكن أن يكون فارغًا",
    "must not be blank": "لا يمكن أن يكون فارغًا",
    "Sign-in is disabled for local development": "تسجيل الدخول متوقف في بيئة التطوير",
    # the daily allowance and the AI provider
    "You’ve reached your daily AI allowance. Please try again after midnight UTC.": "استهلكت رصيدك اليومي من الذكاء الاصطناعي. حاول مرة أخرى بعد منتصف الليل بتوقيت UTC.",
    "You’re sending messages too quickly. Please wait a minute and try again.": "ترسل الرسائل بسرعة كبيرة. انتظر دقيقة ثم حاول مرة أخرى.",
    "The AI provider took too long to reply. Please try again.": "تأخر مزوّد الذكاء الاصطناعي في الرد. حاول مرة أخرى.",
    "Could not reach the AI provider. Please try again.": "تعذّر الوصول إلى مزوّد الذكاء الاصطناعي. حاول مرة أخرى.",
    "The AI provider interrupted the reply. Please try again.": "قطع مزوّد الذكاء الاصطناعي الرد. حاول مرة أخرى.",
    "The AI reply was empty. Please try again.": "وصل الرد فارغًا. حاول مرة أخرى.",
    "The reply was interrupted. Please try again.": "انقطع الرد. حاول مرة أخرى.",
    "This reply reached its length limit and may be incomplete.": "بلغ هذا الرد حدّه الأقصى وقد يكون ناقصًا.",
    "The connection to the AI provider dropped before this reply finished.": "انقطع الاتصال بمزوّد الذكاء الاصطناعي قبل اكتمال الرد.",
    "The AI provider stopped responding before this reply finished.": "توقف مزوّد الذكاء الاصطناعي عن الرد قبل اكتماله.",
    "This reply ran past the time limit and was cut short.": "تجاوز هذا الرد الوقت المسموح فتوقّف قبل اكتماله.",
    "Your reply was saved, but memory could not be updated.": "حُفظ ردك، لكن تعذّر تحديث الذاكرة.",
    # conversations and chat
    "Unknown agent": "زميل غير معروف",
    "Conversation not found": "لم يُعثر على المحادثة",
    "Reply not found": "لم يُعثر على الرد",
    "Message cannot be empty": "لا يمكن أن تكون الرسالة فارغة",
    "Message is required": "الرسالة مطلوبة",
    "Title cannot be empty": "لا يمكن أن يكون العنوان فارغًا",
    "A retry reuses the original message; do not send a new one": "إعادة المحاولة تستخدم الرسالة الأصلية؛ لا ترسل رسالة جديدة",
    "A retry needs the conversation it belongs to": "إعادة المحاولة تحتاج المحادثة التي تنتمي إليها",
    "There is no message to retry.": "لا توجد رسالة لإعادة المحاولة.",
    "The latest reply already finished; there is nothing to retry.": "اكتمل آخر رد بالفعل؛ لا شيء لإعادة المحاولة.",
    "There is no message to take back.": "لا توجد رسالة للتراجع عنها.",
    "The latest message has no reply yet.": "لم يصل رد على آخر رسالة بعد.",
    "That reply has saved content. Remove saved replies, excerpts and comparison notes first.": "لهذا الرد محتوى محفوظ. أزِل الردود والمقتطفات وملاحظات المقارنة المحفوظة أولًا.",
    "conversation belongs to a different agent": "المحادثة تخص زميلًا آخر",
    "Incognito excerpts cannot be saved": "لا يمكن حفظ مقتطفات من محادثة متخفية",
    "Excerpts must contain 1 to 8,000 characters": "يجب أن يكون المقتطف من ١ إلى ٨٬٠٠٠ حرف",
    "This is not a team consultation": "هذه ليست استشارة فريق",
    "The exact passage was not recorded for this reply": "لم يُحفظ المقطع نفسه مع هذا الرد",
    "This source has been deleted": "حُذف هذا المصدر",
    "The source changed; the original passage is unavailable": "تغيّر المصدر؛ المقطع الأصلي غير متاح",
    "Pick each teammate once": "اختر كل زميل مرة واحدة",
    "Leo brings the answers together; pick specialists to ask": "ليو يجمع الإجابات؛ اختر متخصصين لتسألهم",
    "Question cannot be empty": "لا يمكن أن يكون السؤال فارغًا",
    "Ask My Team is not available": "«اسأل فريقك» غير متاح",
    # memory, goals, plans
    "Memory not found": "لم يُعثر على الذكرى",
    "Unknown memory layer": "نوع ذاكرة غير معروف",
    "There is no earlier value to go back to.": "لا توجد قيمة سابقة للرجوع إليها.",
    "Goal not found": "لم يُعثر على الهدف",
    "The end date is before the start date.": "تاريخ النهاية قبل تاريخ البداية.",
    "Follow-up not found": "لم يُعثر على المتابعة",
    "That reply has no steps to keep as a plan.": "لا يحتوي هذا الرد على خطوات تُحفظ كخطة.",
    "Plan not found": "لم يُعثر على الخطة",
    "Step not found": "لم يُعثر على الخطوة",
    "This plan has no dated steps.": "لا تحتوي هذه الخطة على خطوات مؤرخة.",
    "Check-in not found": "لم يُعثر على التسجيل",
    "Privacy notice is unavailable": "إشعار الخصوصية غير متاح",
    # documents and photos
    "Document not found": "لم يُعثر على المستند",
    "That file is over the size limit.": "حجم الملف يتجاوز الحد.",
    "That file is empty.": "الملف فارغ.",
    "Document uploads are switched off on this deployment.": "رفع المستندات متوقف في هذا الخادم.",
    "Only .docx is accepted of the zip-based formats.": "من الصيغ المضغوطة يُقبل ملف ‎.docx فقط.",
    "That image format isn't supported. Use a JPEG, PNG or WebP photo.": "صيغة الصورة غير مدعومة. استخدم صورة JPEG أو PNG أو WebP.",
    "That looks like a binary file. Upload a PDF, DOCX, TXT, MD or a photo.": "يبدو هذا ملفًا ثنائيًا. ارفع PDF أو DOCX أو TXT أو MD أو صورة.",
    "The text file isn't UTF-8. Save it as UTF-8 and try again.": "الملف النصي ليس بترميز UTF-8. احفظه بترميز UTF-8 وحاول مرة أخرى.",
    "The PDF is password-protected.": "ملف PDF محمي بكلمة مرور.",
    "The PDF could not be read.": "تعذّرت قراءة ملف PDF.",
    "The DOCX file is damaged.": "ملف DOCX تالف.",
    "The DOCX file is too large once unpacked.": "ملف DOCX كبير جدًا بعد فك ضغطه.",
    "That zip file is not a Word document.": "هذا الملف المضغوط ليس مستند Word.",
    "The DOCX file contains declarations we don't accept.": "يحتوي ملف DOCX على تعريفات لا نقبلها.",
    "Reading text from photos isn't set up on this server.": "قراءة النص من الصور غير مهيأة على هذا الخادم.",
    "The image could not be opened.": "تعذّر فتح الصورة.",
    "The file took too long to read.": "استغرقت قراءة الملف وقتًا طويلًا.",
    "The file could not be read.": "تعذّرت قراءة الملف.",
    "No readable text found in this file. For a photo or scan, try a sharper, brighter picture taken straight on.": "لم يُعثر على نص مقروء في هذا الملف. للصور والمستندات الممسوحة، جرّب صورة أوضح وأكثر إضاءة ملتقطة من الأمام.",
    "Read from an image, so some words may be wrong. Check anything important.": "قُرئ من صورة، فقد تكون بعض الكلمات خاطئة. تحقّق من أي شيء مهم.",
    "Only the first part of this file was kept: it is very long.": "حُفظ الجزء الأول فقط من هذا الملف: إنه طويل جدًا.",
    # voice
    "Voice input isn't available on this server.": "الإدخال الصوتي غير متاح على هذا الخادم.",
    "Natural voices aren't available on this server.": "الأصوات الطبيعية غير متاحة على هذا الخادم.",
    "That's today's limit for natural voices. The device voice still works.": (
        "هذا حد اليوم للأصوات الطبيعية. صوت الجهاز ما زال يعمل."
    ),
    "Natural voices need to be switched on in the Groq console first.": (
        "يجب تفعيل الأصوات الطبيعية في لوحة Groq أولًا."
    ),
    # reminders, templates, CVs, check-ins
    "Reminders are not available": "التذكيرات غير متاحة",
    "No browser accepted the reminder": "لم يستقبل أي متصفح التذكير",
    "Template not found": "لم يُعثر على القالب",
    "You have the most templates allowed. Delete one first.": (
        "لديك الحد الأقصى من القوالب. احذف واحدًا أولًا."
    ),
    "CV not found": "لم يُعثر على السيرة الذاتية",
    "You have the most CVs allowed. Delete one first.": (
        "لديك الحد الأقصى من السير الذاتية. احذف واحدة أولًا."
    ),
    "That isn't something the team keeps track of.": "هذا ليس مما يتابعه الفريق.",
    "That's today's voice limit. You can still type.": "هذا حد الصوت لليوم. ما زال بإمكانك الكتابة.",
    "That recording is too long. Keep it under a minute.": "التسجيل طويل جدًا. اجعله أقل من دقيقة.",
    "That recording is empty.": "التسجيل فارغ.",
    "That recording format isn't supported.": "صيغة التسجيل غير مدعومة.",
    "Couldn't reach the speech service. Please try again.": "تعذّر الوصول إلى خدمة الصوت. حاول مرة أخرى.",
    "Voice input is at its limit for now. Please type, or try again shortly.": "بلغ الإدخال الصوتي حدّه الآن. اكتب، أو حاول بعد قليل.",
    "Couldn't turn that recording into text. Please try again.": "تعذّر تحويل التسجيل إلى نص. حاول مرة أخرى.",
}

_PATTERNS: list[tuple[re.Pattern[str], callable]] = [
    (re.compile(r"^Unknown agent: (.+)$"), lambda m: f"زميل غير معروف: {m.group(1)}"),
    (
        re.compile(r"^That file is over the (\d+) MB limit\.$"),
        lambda m: f"حجم الملف يتجاوز {num(int(m.group(1)))} ميغابايت.",
    ),
    (
        re.compile(r"^You can keep up to (\d+) documents\. Delete one to add another\.$"),
        lambda m: f"يمكنك الاحتفاظ بـ{num(int(m.group(1)))} مستندات كحد أقصى. احذف واحدًا لتضيف آخر.",
    ),
    (
        re.compile(r"^The AI provider could not respond \(HTTP (\d+)\)\. Please try again later\.$"),
        lambda m: f"تعذّر على مزوّد الذكاء الاصطناعي الرد (HTTP {m.group(1)}). حاول لاحقًا.",
    ),
    (
        re.compile(r"^The AI provider is at its usage limit\. Please try again in about (\d+) minutes?\.$"),
        lambda m: f"بلغ مزوّد الذكاء الاصطناعي حدّ الاستخدام. حاول مرة أخرى بعد نحو {num(int(m.group(1)))} دقيقة.",
    ),
    (
        re.compile(r"^The AI provider is at its usage limit\. Please try again later\.$"),
        lambda m: "بلغ مزوّد الذكاء الاصطناعي حدّ الاستخدام. حاول لاحقًا.",
    ),
    (
        re.compile(r"^Use at least (\d+) characters\.$"),
        lambda m: f"استخدم {num(int(m.group(1)))} أحرف على الأقل.",
    ),
    (
        re.compile(r"^Use at most (\d+) characters\.$"),
        lambda m: f"استخدم {num(int(m.group(1)))} حرفًا على الأكثر.",
    ),
    (
        re.compile(r"^At most (\d+) profile fields$"),
        lambda m: f"{num(int(m.group(1)))} حقلًا كحد أقصى في الملف",
    ),
    (
        re.compile(r"^Profile values must be at most (\d+) characters$"),
        lambda m: f"يجب ألا تتجاوز قيم الملف {num(int(m.group(1)))} حرف",
    ),
]  # fmt: skip


def translate(text: str, locale: str) -> str:
    """The Arabic of a message this server wrote, or the message unchanged."""
    if locale != "ar" or not isinstance(text, str) or not text:
        return text
    exact = _ARABIC.get(text)
    if exact:
        return exact
    for pattern, render in _PATTERNS:
        match = pattern.match(text)
        if match:
            return render(match)
    return text


def translate_detail(detail, locale: str):
    """An HTTP error's detail: a sentence, or FastAPI's list of field errors."""
    if locale != "ar":
        return detail
    if isinstance(detail, str):
        return translate(detail, locale)
    if isinstance(detail, list):
        out = []
        for item in detail:
            if isinstance(item, dict) and isinstance(item.get("msg"), str):
                msg = item["msg"].removeprefix("Value error, ")
                translated = translate(msg, locale)
                item = {**item, "msg": translated if translated != msg else item["msg"]}
            out.append(item)
        return out
    return detail


# --- the weekly summary -----------------------------------------------------------------


def week_summary(review: dict, today: date) -> str:
    """The Arabic of tracking.service.weekly_review's summary, from its fields."""
    last: list[str] = []
    steps = review.get("plan_steps_done") or 0
    if steps:
        last.append(f"أُنجزت {num(steps)} من خطوات الخطط")
    checkins = sum((review.get("checkins") or {}).values())
    if checkins:
        last.append(f"سُجّل {num(checkins)} من التقدّم")
    if review.get("goals_done"):
        last.append("اكتمل هدف: " + "، ".join(review["goals_done"][:3]))
    if review.get("followups_passed"):
        last.append("مرّ: " + "، ".join(review["followups_passed"][:3]))
    spending = review.get("spending") or {}
    if spending:
        last.append(
            "المصروف: "
            + "، ".join(
                num(total) if cur.startswith("no ") else f"{num(total)} {cur}"
                for cur, total in spending.items()
            )
        )
    nxt = [
        f"{item['title']} {countdown(date.fromisoformat(item['due_on']), today)}"
        for item in (review.get("coming_up") or [])[:3]
    ]
    if review.get("quiet_goals"):
        nxt.append("لم يتحرك مؤخرًا: " + "، ".join(review["quiet_goals"]))
    due = review.get("plan_steps_due") or 0
    if due:
        nxt.append(f"{num(due)} من خطوات الخطط مستحقة")
    if not last and not nxt:
        return "لم يُسجَّل شيء بعد. احفظ خطة، أو اذكر موعدًا، أو أخبر زميلًا بما أنجزت، وسيظهر أسبوعك هنا."
    first = ("آخر ٧ أيام: " + "؛ ".join(last) + ". ") if last else "أسبوع هادئ. "
    second = ("الأيام السبعة القادمة: " + "؛ ".join(nxt) + ".") if nxt else "لا شيء مؤرخ بعد."
    return first + second
