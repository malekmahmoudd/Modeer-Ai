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
    # money: income and balances, not budgets or spending preferences
    r"salary", r"income", r"i earn", r"earnings", r"net worth", r"debts?",
    r"bank account", r"account number", r"iban", r"sort code", r"credit score",
    r"credit card", r"card number", r"bankrupt\w*", r"balance of",
    # government identifiers
    r"passport", r"social security", r"ssn", r"national insurance", r"national id",
    r"id number", r"tax id", r"driver'?s licen[cs]e",
    # credentials
    r"passwords?", r"passcode", r"pin (?:code|number)", r"api key", r"secret key",
    # belief, identity, status, history
    r"religio\w*", r"faith", r"muslim", r"christian", r"catholic", r"jewish", r"hindu",
    r"buddhist", r"sikh", r"atheist", r"sexual orientation", r"sexuality", r"gay",
    r"lesbian", r"bisexual", r"transgender", r"queer", r"political", r"immigration status",
    r"asylum", r"refugee", r"undocumented", r"residence permit", r"criminal record",
    r"convicted", r"conviction", r"arrested", r"prison",
]
# fmt: on
_SENSITIVE = re.compile(r"\b(?:" + "|".join(_TERMS) + r")\b", re.IGNORECASE)


def looks_sensitive(*texts: str | None, category: str | None = None) -> bool:
    """True when a category or any text suggests sensitive personal data.

    Conservative by design: a hit withholds the fact from automatic storage;
    a miss proves nothing.
    """
    if category and category.lower() in SENSITIVE_CATEGORIES:
        return True
    return any(_SENSITIVE.search(text) for text in texts if text)
