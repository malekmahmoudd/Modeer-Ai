"""Response-quality rubric.

The keyword scoring in :mod:`app.agents.evals` answers "did the reply mention the
right words". That question is too easy: it passed a biography full of invented
achievements, a study plan that guessed a month and then withheld itself, and a
shopping answer that quoted stale prices with confidence.

This module grades the reply instead of its vocabulary, in two layers:

* :func:`review` — deterministic checks that need no provider, so they run in CI
  against the mock and stay cheap. They only cover what can be detected with high
  precision: withheld plans, invented months, capability claims, unhedged prices,
  unrequested rationale, verbosity, per-case forbidden phrases.
* :func:`judge` — an LLM judge for what a regex cannot see: facts invented about
  the user, stale specifics stated as current, ignored preferences. It quotes the
  offending span so a human can check the verdict rather than trust a score.

A case passes only when both layers pass.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field

from app.llm.base import LLMMessage, LLMProvider

RUBRIC_DIMENSIONS = [
    "relevance",
    "specialization",
    "usefulness",
    "clarity",
    "personalization",
    "scope_discipline",
    "safety",
]

#: Judgement dimensions the LLM judge scores. Each is phrased so that "pass"
#: means the reply is acceptable, and every failure must quote its evidence.
JUDGE_DIMENSIONS: dict[str, str] = {
    "grounding": (
        "Every concrete claim about the user (achievements, expertise, metrics, "
        "employer activity, schedule, dates, hobbies, contact details, pronouns) "
        "is supported by the supplied context, is an explicit [placeholder], or is "
        "labelled as an assumption. A job title alone is NOT evidence of any "
        "achievement or specialism. Judge only claims about THIS PERSON: general "
        "domain knowledge, worked examples with invented round numbers, and "
        "statements the reply itself marks as an assumption or example all pass. "
        "An unlabelled constraint the user never gave — a budget, a deadline, an "
        "affordability limit — presented as theirs is the failure to catch."
    ),
    "delivers": (
        "If the user asked for a plan, draft, itinerary or recommendation, the "
        "reply contains a usable first version NOW. Judge only whether the "
        "deliverable is present. A reply that contains the draft and then asks a "
        "clarifying question PASSES — closing questions are wanted, and are never "
        "on their own a reason to fail this dimension. Fail it only when the "
        "deliverable is absent or postponed to a later turn."
    ),
    "currency": (
        "No claim that depends on information the assistant cannot have — current "
        "prices, stock, which product generation is newest, live schedules — is "
        "stated as current fact. Naming a product is fine; asserting it is the "
        "latest, or quoting today's price, is not. These all PASS and are not "
        "your concern: a price range, a figure hedged with 'typically', 'around' "
        "or '≈', a budget the reply allocates, a worked example introduced by "
        "'if' or 'example', a column header, and telling the user to go and check "
        "the current price. Fail only a bare figure asserted as what something "
        "costs right now."
    ),
    "respects_preferences": (
        "The reply honours the stated preferences and constraints in the context "
        "and contradicts none of them."
    ),
    "capability_honesty": (
        "The reply never implies it can browse, book, purchase, send, or check anything live. "
        "Suggesting the user speak to another named specialist in the app is allowed; "
        "this is advice, not evidence of browsing or performing an external action."
    ),
    "concision": (
        "Length matches the request. No filler, no restating the context back, no "
        "unrequested explanation of why the answer is good."
    ),
}

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
#: A date fact with a day but no month, e.g. "thermodynamics final on the 20th".
_BARE_ORDINAL_DATE = re.compile(r"\bon the \d{1,2}(st|nd|rd|th)\b", re.I)
_MONTH_MENTION = re.compile(rf"\b({_MONTHS})\b", re.I)
#: Counting the gap between today and a date the user gave — "today is day 1 of a
#: 14-day countdown", "you have 10 days until the final". The agent cannot see
#: today's date, so the interval is invented no matter how it is hedged, and the
#: whole plan is then built on it.
_ASSUMED_INTERVAL = re.compile(
    # Anchoring today to a step of the plan is the root error; the noun that
    # follows ("countdown", "cycle", "window") is incidental, so match the anchor.
    r"\btoday is\s+(?:the\s+)?(?:day|week)\s*\d"
    r"|\b\d{1,3}[- ](?:day|week) (?:countdown|cycle|window|sprint|stretch|period|run)\b"
    r"|\b(?:you have|that (?:gives|leaves) (?:you|us)|there are|we have)\s+"
    r"(?:about |roughly |approximately )?\d{1,3}\s+(?:days|weeks)\b"
    r"|\b\d{1,3}\s+(?:days|weeks)\s+(?:until|before|away|left|to go|out from)\b",
    re.I,
)

#: Phrases that claim an action or lookup the assistant cannot perform. Every
#: alternative needs a first-person subject: "Check current prices" is the agent
#: correctly handing the job back to the user, and a bare noun-phrase version of
#: this pattern failed Shopping for saying exactly the right thing.
_CAPABILITY_CLAIM = re.compile(
    r"\b("
    r"i(?:'ll| will| have| can| just)? ?(?:book|booked|booking|purchase[d]?|order[ed]?)\b"
    r"|i (?:checked|searched|looked up|browsed|found online|verified)\b"
    r"|i(?:'ve| have) (?:sent|emailed|scheduled)\b"
    r"|(?:i|we) (?:can |could |just )?(?:see|checked?|pulled) "
    r"(?:the )?(?:current|live|today'?s|latest) "
    r"(?:price|prices|stock|availability|rates)\b"
    r"|as of (?:today|now|this (?:week|month))\b"
    r")",
    re.I,
)

#: Headings the model adds to explain its own work when nobody asked.
_UNREQUESTED_RATIONALE = re.compile(
    r"^\W*\**\s*(why (this|it) (works|structure|is|matters)"
    r"|rationale|reasoning|notes on (the|this) (draft|structure)"
    r"|what (this|i) (did|changed)|design notes)\b",
    re.I | re.M,
)

_CURRENCY = re.compile(r"[£$€]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*\s?(?:usd|gbp|eur)\b", re.I)
#: Models hedge with a symbol as often as a word — "≈£120/night", "~£45".
_APPROX_SYMBOL = re.compile(r"[≈~∼]\s?[£$€]?\s?\d")
#: A price stated as fact: something costs, retails at, or sells for a figure.
#: A bare amount in a budget line or an itinerary cell asserts nothing.
_PRICE_ASSERTION = re.compile(
    r"\b(?:costs?|retails?(?:\s+(?:at|for))?|sells?\s+for|is\s+priced\s+at|"
    r"goes?\s+for|comes?\s+in\s+at|price\s+is|priced\s+at)\s+"
    r"(?:about\s+|around\s+)?[£$€]\s?\d",
    re.I,
)
_HEDGE = re.compile(
    r"\b(typically|roughly|around|approximately|about|varies|varied|range[sd]?|"
    r"ballpark|order of|check (?:current|the current|today)|verify|confirm|"
    r"depend(?:s|ing)|estimate[sd]?|budget|under|below|over|often|usually|"
    r"up to|at least|e\.?g\.?|"
    r"for example|example|say|if|assume|suppose|ceiling|limit)\b",
    re.I,
)
#: A span like "£350-£400" or "£80 to £130" is self-evidently an estimate, so it
#: needs no other hedge. Only a bare single figure asserts a price as fact.
#: Models emit non-breaking hyphens (U+2011) and figure dashes, so match those too.
_PRICE_RANGE = re.compile(
    r"[£$€]\s?\d[\d,]*(?:\.\d+)?\s*(?:[-‐-―]|to)\s*[£$€]?\s?\d",
    re.I,
)
#: "a €250,000 flat" posits an instance; "the iPhone 15 costs £799" asserts a
#: price. The indefinite article is the difference, and it is the difference
#: between a worked example and a claim about a market the agent cannot see.
_HYPOTHETICAL_AMOUNT = re.compile(r"\ban?\s+[£$€]\s?\d", re.I)
#: A budget line — "- **Buffer:** £50", "10% Deposit: €30,000", "- 5% Buffer
#: (€15,000): fees" — is the agent allocating money inside a plan it was asked
#: for, not asserting what something costs in a shop today. A labelled item in a
#: breakdown reads as structure; only running prose makes a market claim.
_BUDGET_LINE = re.compile(
    r"^\s*(?:[-*•]|\d+[.)]|\|)\s*[^\n]*?:"  # a list item carrying a label
    r"|^\s*[^.:\n]{0,60}:\s*\**\s*[£$€]?\s?\d",  # or "Label: £50" on its own line
    re.M,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_STRUCTURE_LINE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|#{1,6}\s|\*\*)", re.M)

#: Words that signal the user is asking for something to be produced.
_DELIVERABLE_REQUEST = re.compile(
    r"\b(plan|itinerary|draft|write|recommend|suggest|outline|schedule|routine|"
    r"budget|strategy|template)\w*\b",
    re.I,
)
_ASKED_FOR_REASONS = re.compile(r"\b(why|explain|rationale|reason|justify)\b", re.I)

#: A request for a piece of text the user will use as-is. Commentary on top of an
#: artifact is padding; commentary on top of advice is the advice, so the
#: unrequested-rationale check only applies to the first kind.
_ARTIFACT_REQUEST = re.compile(
    r"\b(draft|write|rewrite|edit|bio|biography|email|message|letter|post|"
    r"caption|summary|abstract|cover letter|intro)\w*\b",
    re.I,
)

#: "Once I know X, I'll draft the itinerary" — the deliverable postponed to a
#: turn that may never come. Travel and Shopping both did this.
_DEFERRED_PROMISE = re.compile(
    r"\b(once|after|as soon as|when) (i|you|we) (know|have|get|confirm|tell|share|provide)\b"
    r"[^.!?\n]{0,120}?\b(i|we)(?:'ll| will| can)\b"
    r"|\b(i|we)(?:'ll| will| can) (?:then )?(?:draft|build|put together|create|map out|"
    r"narrow|design|prepare|sketch)\b[^.!?\n]{0,80}?\b(once|after|when|as soon as)\b",
    re.I,
)

#: An interrogation does not need question marks. Shopping asked for everything
#: it needed as a numbered list of statements — "1. What you mainly use a phone
#: for." — and slipped past a check that only counted "?".
_INFO_REQUEST = re.compile(
    r"\b(?:i|we)(?:'d)?\s+(?:need|want|would (?:need|like))\s+to\s+know\b"
    r"|\bcould you (?:tell|let) me\b"
    r"|\b(?:tell|let) me\b[^.!?\n]{0,40}\b(?:more about|a bit more|the following)\b"
    r"|\bbefore (?:i|we) can\b[^.!?\n]{0,60}\b(?:recommend|suggest|draft|plan|build)\b"
    r"|\byour answers will\b"
    r"|\bwith (?:those|these) answers\b"
    r"|\b(?:a few|some) (?:quick )?questions\b",
    re.I,
)

#: Ordinary answers longer than this read as padded rather than thorough. A case
#: whose deliverable is genuinely long (a week of training, a two-week syllabus)
#: raises it with ``expect.max_words`` rather than dropping the check.
DEFAULT_MAX_WORDS = 350


@dataclass(slots=True)
class Violation:
    """One concrete quality defect, with the text that triggered it."""

    code: str
    detail: str
    evidence: str = ""

    def __str__(self) -> str:
        tail = f" — {self.evidence.strip()[:120]}" if self.evidence else ""
        return f"- {self.code}: {self.detail}{tail}"


@dataclass(slots=True)
class Review:
    """Deterministic verdict for a single response."""

    passed: bool
    words: int
    violations: list[Violation] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "words": self.words,
            "violations": [asdict(v) for v in self.violations],
        }


def _context_values(case: dict) -> list[str]:
    rows = [*case.get("shared_context", []), *case.get("agent_memory", [])]
    return [str(r.get("value", "")) for r in rows]


def _looks_like_a_deliverable(text: str) -> bool:
    """True when the reply hands something over rather than interviewing the user.

    Short is not the same as absent: a good conference bio is forty words. So
    length alone never condemns a reply — only a promise to deliver later, or a
    reply made mostly of questions, does.
    """
    if _DEFERRED_PROMISE.search(text):
        # "Once I know those, I'll draft the itinerary" — a bulleted list of
        # questions still counts as structure, so this has to be checked first.
        return False
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    # A reply that opens by asking for information is interviewing the user
    # whether or not it punctuates the requests as questions, so everything it
    # asks for counts against it the same way.
    asking = bool(_INFO_REQUEST.search(text))
    questions = [s for s in sentences if s.endswith("?")]
    if not questions and not asking:
        return True
    statements = [s for s in sentences if not s.endswith("?")]
    if asking and not questions:
        # Nothing is punctuated as a question, so fall back to whether real
        # content survives once the request framing and its list are removed.
        return sum(len(s.split()) for s in statements if not _INFO_REQUEST.search(s)) >= 90
    body = "\n".join(line for line in text.splitlines() if not line.strip().startswith(("?", ">")))
    if len(_STRUCTURE_LINE.findall(body)) >= 3 and len(statements) > len(questions):
        return True
    return sum(len(s.split()) for s in statements) >= 40


def review(case: dict, output: str, *, max_words: int = DEFAULT_MAX_WORDS) -> Review:
    """Grade ``output`` with checks that need no provider and no human.

    Every check here is deliberately high-precision: a violation should mean a
    real defect, because these gate CI. Judgement calls belong in :func:`judge`.
    """
    expect = case.get("expect", {})
    text = output.strip()
    words = len(text.split())
    violations: list[Violation] = []

    if not text:
        return Review(passed=False, words=0, violations=[Violation("empty", "no response")])

    # A plan that is only a list of questions is the failure we saw from Study
    # and Research: the user asked for the plan and got an interview instead.
    wants_deliverable = expect.get("delivers", bool(_DELIVERABLE_REQUEST.search(case["input"])))
    if wants_deliverable and not _looks_like_a_deliverable(text):
        violations.append(
            Violation(
                "withheld_deliverable",
                "asked for something concrete but the reply only asks questions",
                text[:160],
            )
        )

    # Study invented "March" from a context that only said "on the 20th".
    bare_date = any(_BARE_ORDINAL_DATE.search(v) for v in _context_values(case))
    if bare_date and (month := _MONTH_MENTION.search(text)):
        violations.append(
            Violation(
                "invented_month",
                "named a month the supplied date never specified",
                month.group(0),
            )
        )

    # Study built a whole two-week plan on "today is day 1 of a 14-day countdown".
    if bare_date and (interval := _ASSUMED_INTERVAL.search(text)):
        violations.append(
            Violation(
                "assumed_interval",
                "counted the gap to a date it cannot place in the calendar",
                interval.group(0),
            )
        )

    if claim := _CAPABILITY_CLAIM.search(text):
        violations.append(
            Violation(
                "capability_claim",
                "implies an action or lookup the assistant cannot perform",
                claim.group(0),
            )
        )

    # Only an asserted price counts here: something *costs* a figure. Money
    # appears constantly in these answers as budget lines, tips, worked examples
    # and allocations, and every looser version of this check produced more false
    # positives than findings. Staleness that a regex cannot see -- "the typical
    # Dublin flat price today" -- is the judge's `currency` dimension, which
    # catches it with the context a pattern does not have.
    for sentence in _SENTENCE_SPLIT.split(text):
        if (
            _PRICE_ASSERTION.search(sentence)
            and not _PRICE_RANGE.search(sentence)
            and not _HYPOTHETICAL_AMOUNT.search(sentence)
            and not _APPROX_SYMBOL.search(sentence)
            and not _HEDGE.search(sentence)
        ):
            violations.append(
                Violation("unhedged_price", "states a price as fact", sentence.strip())
            )
            break

    # Writing kept appending "Why this structure" to drafts nobody asked to have
    # explained.
    wants_artifact = expect.get("artifact", bool(_ARTIFACT_REQUEST.search(case["input"])))
    if (
        wants_artifact
        and not _ASKED_FOR_REASONS.search(case["input"])
        and (heading := _UNREQUESTED_RATIONALE.search(text))
    ):
        violations.append(
            Violation(
                "unrequested_rationale",
                "explains its own work when the user only asked for the work",
                heading.group(0).strip(),
            )
        )

    cap = expect.get("max_words", max_words)
    if words > cap:
        violations.append(Violation("too_long", f"{words} words against a {cap}-word ceiling"))

    # Word boundaries, not substrings: "Friday-to-Sunday trip" contains the
    # letters of "day trip" and failed a perfectly good single-city itinerary.
    for phrase in expect.get("must_avoid", []):
        pattern = r"\b" + r"[\s-]+".join(re.escape(w) for w in phrase.split()) + r"\b"
        if found := re.search(pattern, text, re.I):
            violations.append(
                Violation("ignored_constraint", "contradicts a stated preference", found.group(0))
            )

    return Review(passed=not violations, words=words, violations=violations)


_JUDGE_SYSTEM = """\
You grade one reply from a personal-assistant agent. You are strict, concrete and
you never reward fluent writing that is unsupported.

The agent has no internet, no tools and no knowledge of today's date. It knows
only the CONTEXT given below. Anything about the user that is not in CONTEXT is
invented unless the reply marks it as a placeholder or a stated assumption.

Return ONLY a JSON object, no prose, no code fence:
{"dimensions": {"<name>": {"pass": true|false, "evidence": "<quote or empty>"}},
 "worst_problem": "<one sentence, or empty when nothing failed>"}

Judge exactly these dimensions:
%s

Rules:
- "pass": false REQUIRES a verbatim quote from the reply in "evidence".
- Judge only what the reply says. Do not reward or punish formatting.
- A reply that admits it does not know something is correct behaviour, not a failure.
"""


@dataclass(slots=True)
class Judgement:
    """LLM-judge verdict. ``available`` is False when the judge itself failed."""

    passed: bool
    available: bool
    dimensions: dict[str, dict] = field(default_factory=dict)
    worst_problem: str = ""
    error: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _judge_prompt(case: dict, output: str) -> str:
    rows = [*case.get("shared_context", []), *case.get("agent_memory", [])]
    context = "\n".join(f"- {r.get('key')}: {r.get('value')}" for r in rows) or "- (nothing known)"
    profile = json.dumps(case.get("profile", {}), ensure_ascii=False)
    name = case.get("display_name", "(not supplied)")
    return (
        f"PROFILE: display_name={name}; profile={profile}\n"
        f"CONTEXT (everything the agent knows about the user):\n{context}\n\n"
        f"USER ASKED:\n{case['input']}\n\n"
        f"REPLY TO GRADE:\n{output}"
    )


def _parse_judgement(raw: str, expected: set[str] | None = None) -> Judgement:
    body = raw.strip()
    if body.startswith("```"):
        body = body.strip("`")
        body = body.split("\n", 1)[1] if "\n" in body else body
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end == -1:
        return Judgement(passed=False, available=False, error="judge returned no JSON")
    try:
        data = json.loads(body[start : end + 1])
    except ValueError as exc:
        return Judgement(passed=False, available=False, error=f"unparsable judge JSON: {exc}")
    supplied = data.get("dimensions") if isinstance(data, dict) else None
    if not isinstance(supplied, dict) or (expected is not None and set(supplied) != expected):
        return Judgement(
            passed=False, available=False, error="judge dimensions missing or unexpected"
        )
    if any(not isinstance(v, dict) or type(v.get("pass")) is not bool for v in supplied.values()):
        return Judgement(
            passed=False, available=False, error="judge verdict must use JSON booleans"
        )
    dimensions = {
        name: {"pass": v["pass"], "evidence": str(v.get("evidence", ""))}
        for name, v in (data.get("dimensions") or {}).items()
        if isinstance(v, dict)
    }
    if not dimensions:
        return Judgement(passed=False, available=False, error="judge returned no dimensions")
    return Judgement(
        passed=all(d["pass"] for d in dimensions.values()),
        available=True,
        dimensions=dimensions,
        worst_problem=str(data.get("worst_problem", "")),
    )


async def judge(
    case: dict,
    output: str,
    *,
    provider: LLMProvider,
    model: str,
) -> Judgement:
    """Ask ``model`` to grade ``output`` against :data:`JUDGE_DIMENSIONS`."""
    if not output.strip():
        return Judgement(passed=False, available=True, worst_problem="empty response")
    dimensions = dict(JUDGE_DIMENSIONS)
    if not _DELIVERABLE_REQUEST.search(case["input"]):
        # Nothing was asked for, so there is nothing to withhold. Weaker judge
        # models otherwise fail "I do not know" for not delivering a plan.
        dimensions.pop("delivers", None)
    spec = "\n".join(f"- {name}: {desc}" for name, desc in dimensions.items())
    for attempt in range(3):
        try:
            result = await provider.complete(
                system=_JUDGE_SYSTEM % spec,
                messages=[LLMMessage(role="user", content=_judge_prompt(case, output))],
                model=model,
                temperature=0.0,
                max_tokens=700,
            )
            break
        except Exception as exc:  # Judge outages must not look like answer failures.
            wait = getattr(exc, "retry_after", None)
            if attempt < 2 and wait is not None and 0 < wait <= 60:
                await asyncio.sleep(wait + 1)
                continue
            return Judgement(passed=False, available=False, error=f"{type(exc).__name__}: {exc}")
    return _parse_judgement(result.text, set(dimensions))
