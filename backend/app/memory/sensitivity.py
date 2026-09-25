"""A conservative backstop for sensitive personal data in automatic memory.

Automatic extraction asks the model to flag sensitive facts, but a model flag is
a suggestion, not a control: it can be missing, the wrong type, or simply wrong.
This module is the second opinion. It errs towards withholding.

It is a KEYWORD BACKSTOP, not a classifier. It will miss sensitive facts phrased
in words it does not list, and it will occasionally withhold a harmless one. It
reduces the chance that health, money, identity or belief details are stored
without consent; it cannot guarantee that none are. The consent model it serves
is the deployment-level ``MEMORY_STORE_SENSITIVE`` opt-in (off by default) plus
the user's own explicit saves, which never pass through here.

The categories mirror the extraction prompt's own definition — health
conditions, medications, income and balances, government IDs, credentials,
religion, immigration status, sexuality — plus criminal history and politics.
"""

from __future__ import annotations

import re

#: Categories whose contents are sensitive by nature. "health" covers conditions
#: and treatment; ordinary training routines belong in "routine".
SENSITIVE_CATEGORIES = frozenset({"health"})

# Grouped by kind; the formatter's one-term-per-line would bury the grouping.
# fmt: off
_TERMS = [
    # health: conditions, treatment, reproductive health, disability
    r"diagnos\w*", r"disorders?", r"depress\w*", r"anxiety", r"adhd", r"autis\w*",
    r"bipolar", r"schizo\w*", r"ptsd", r"ocd", r"anorexi\w*", r"bulimi\w*",
    r"hiv", r"aids", r"cancer", r"tumou?rs?", r"diabet\w*", r"asthma", r"epilep\w*",
    r"chronic", r"illness(?:es)?", r"diseases?", r"medications?", r"prescri\w*",
    r"antidepressants?", r"therap(?:y|ist)", r"psychiatr\w*", r"counsell?ing",
    r"rehab\w*", r"addict\w*", r"surgery", r"pregnan\w*", r"miscarriage", r"abortion",
    r"disabilit\w*", r"disabled", r"injur(?:y|ies|ed)",
    # injuries, symptoms and care — a sports physio found the list above caught
    # 4 of 72 everyday phrasings ("torn ACL", "physio appointment", "MRI")
    r"pain(?:s|ful|killers?)?", r"sore", r"torn", r"sprain\w*", r"fractur\w*", r"ruptur\w*",
    r"concussion", r"herniat\w*", r"shin splints", r"plantar fasci\w*", r"acl",
    r"physio\w*", r"doctor", r"gp", r"hospital", r"clinic", r"surgeon", r"post-op",
    r"operation", r"mri", r"x-?rays?", r"ct scan", r"biopsy", r"blood (?:test|pressure|sugar)",
    r"hypertension", r"arrhythmia", r"heart (?:condition|disease|attack|problem)",
    r"faint\w*", r"dizz\w*", r"insulin", r"ozempic", r"steroids?", r"meds", r"pills?",
    r"arthritis", r"osteopor\w*", r"migraines?", r"ibs", r"long covid", r"chemo\w*",
    r"dentist", r"cardiolog\w*", r"psycholog\w*", r"counsell?or",
    # reproductive health
    r"ivf", r"fertility", r"postpartum", r"pelvic floor", r"menopaus\w*", r"period pain",
    # eating, weight and restriction: never tracked or stored automatically
    r"binge\w*", r"purg\w*", r"calories?", r"kcal", r"fasted", r"fasting",
    r"weigh(?:ed|-in| in)", r"bmi", r"allerg\w*", r"coeliac", r"celiac", r"intoleran\w*",
    # crisis and safeguarding
    r"suicid\w*", r"self[- ]harm\w*", r"abus(?:e|ed|ive)", r"overdos\w*", r"relapse\w*",
    r"sober", r"aa meeting",
    # life events it is not our place to follow up on uninvited
    r"funeral", r"memorial", r"bereave\w*", r"passed away", r"grief", r"divorce\w*",
    r"custody", r"court", r"lawsuit", r"evict\w*", r"gambl\w*", r"payday loan",
    # money: income and balances, not budgets or spending preferences
    r"salary", r"income", r"i earn", r"earnings", r"net worth", r"debts?",
    r"bank account", r"account number", r"iban", r"sort code", r"credit score",
    r"credit card", r"card number", r"bankrupt\w*", r"balance of",
    r"paycheck", r"payslip", r"wages?", r"mortgage", r"loans?", r"overdraft",
    # government identifiers
    r"passport", r"social security", r"ssn", r"national insurance", r"national id",
    r"id number", r"tax id", r"driver'?s licen[cs]e", r"date of birth",
    r"home address", r"phone number", r"iqama", r"emirates id", r"civil id",
    r"visa status", r"kafala", r"gdrfa", r"absher",
    # credentials
    r"passwords?", r"passcode", r"pin (?:code|number)", r"api key", r"secret key",
    # belief, identity, status, history
    r"religio\w*", r"faith", r"muslim", r"christian", r"catholic", r"jewish", r"hindu",
    r"buddhist", r"sikh", r"atheist", r"halal", r"kosher", r"shia", r"sunni",
    r"sexual orientation", r"sexuality", r"gay",
    r"lesbian", r"bisexual", r"transgender", r"queer", r"political", r"immigration status",
    r"asylum", r"refugee", r"undocumented", r"residence permit", r"criminal record",
    r"convicted", r"conviction", r"arrested", r"prison",
]
# Arabic, matched after normalisation (see _fold). Stems, so no \b on the left:
# Arabic attaches "al-", "wa-", "bi-" and "li-" to the front of a word.
_ARABIC_STEMS = [
    # health and care
    "مرض", "سكري", "اكتئاب", "طبيب نفسي", "علاج نفسي", "مرض نفسي", "دواء", "ادويه",
    "مستشفي", "طبيب", "دكتور", "عمليه جراحيه", "اصابه", "تحليل دم", "اشعه", "حامل",
    "اعاقه", "انتحار", "ايذاء النفس", "سعرات", "رجيم قاسي", "وزني", "حساسيه",
    # money
    "راتب", "مرتب", "دخلي", "ديون", "قرض", "حساب بنكي", "ايبان",
    # identity documents and status
    "هويه", "جواز", "اقامه", "تاشيره", "لجوء", "كفيل",
    # belief and identity
    "ديانه", "مسلم", "مسيحي", "شيعي", "ملحد", "مثلي",
    # credentials
    "كلمه المرور", "كلمه السر",
    # life events
    "جنازه", "عزاء", "وفاه", "طلاق", "محكمه", "حضانه", "سجن",
]
# fmt: on
_SENSITIVE = re.compile(r"\b(?:" + "|".join(_TERMS) + r")\b", re.IGNORECASE)
_SENSITIVE_AR = re.compile("|".join(map(re.escape, _ARABIC_STEMS)))
_ARABIC_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ـ": None})
_DIACRITICS = re.compile(r"[\u064b-\u0652\u0670]")


def _fold(text: str) -> str:
    """Arabic spelled one way: alef forms, taa marbuta, alef maqsura, no tatweel
    or short vowels. "المستشفى" and "مستشفي" then match the same stem."""
    return _DIACRITICS.sub("", text).translate(_ARABIC_FOLD)


def looks_sensitive(*texts: str | None, category: str | None = None) -> bool:
    """True when a category or any text suggests sensitive personal data.

    Conservative by design: a hit withholds the fact from automatic storage;
    a miss proves nothing.
    """
    if category and category.lower() in SENSITIVE_CATEGORIES:
        return True
    return any(
        _SENSITIVE.search(text) or _SENSITIVE_AR.search(_fold(text)) for text in texts if text
    )
