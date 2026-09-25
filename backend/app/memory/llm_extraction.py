"""LLM-assisted memory extraction.

Used when a real provider is configured (see ``settings.use_llm_extraction``).
The model proposes durable facts; the *same* conservative gates as the rule-based
path then decide what is actually stored (sensitive data dropped unless the user
opted in, low-confidence dropped, agent-scoped facts kept only in-domain).

One short JSON call per user message, and only when the message could hold
something to act on (see :func:`worth_analyzing`). The same call also picks up
explicit requests to change goals (Leo only) and to hand something to a
teammate; see :func:`analyze_turn`. Any failure falls back to the rule-based
extractor so a bad response never breaks a turn.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from app.core.config import settings
from app.llm.base import LLMMessage, LLMProvider
from app.memory.extraction import Candidate, extract_candidates
from app.memory.keys import canonical_keys
from app.memory.pasted import is_about_me, strip_pasted
from app.memory.sensitivity import looks_sensitive

_SYSTEM = """You extract durable personal facts from a user's message so a
personal-assistant team can remember them long-term.

Return ONLY a JSON object (no prose, no markdown fences):
{"facts": [<fact>, ...]%(extra_keys)s}
Each fact:
{"scope": "shared" | "agent",
 "agent_id": "<specialist slug, or null when scope is shared>",
 "category": "one of: education, career, goals, context, preferences, health,
              finance, routine, targets, weak_topics, general",
 "key": "snake_case_stable_key",
 "value": "concise factual value",
 "confidence": 0.0-1.0,
 "sensitive": true|false}

What counts as DURABLE (capture it):
- Identity & situation: studies, job, location, languages, age.
- Goals, plans and deadlines — including future-dated ones. "ML internship next
  summer", "trip to Japan in April", "exam on the 20th" are goals, not transient.
- Stable preferences, routines and hobbies: "trains 4x/week", "vegetarian",
  "learns best from examples", "budget around $1000".
- Constraints: "can't relocate", "no early flights", "works night shifts".

What is TRANSIENT (ignore it): mood or energy right now ("tired today"), what
they're doing this minute, pleasantries, and one-off questions with no lasting
fact in them.

Scope:
- "shared" = useful to several specialists (identity, goals, big preferences).
- "agent" + agent_id = domain-specific detail only that specialist needs. Slugs:
  study, career, travel, shopping, finance, fitness, writing, research, email.
  e.g. powerlifting routine -> {"scope":"agent","agent_id":"fitness",...}

Other rules:
- Only facts the user states about THEMSELVES. Nothing about other people, and
  nothing from text they quote, paste or forward (shown as [pasted text omitted]).
- Split a compound sentence into separate facts. Keep values short and factual.
- Reuse a known key when the fact is the same kind of thing: %(keys)s.%(dates)s
- sensitive=true for health conditions, medications, income/balances, government
  IDs, credentials, religion, immigration status, sexuality. Still report them.
- If the message contains no durable fact, "facts" is [].%(sections)s

Example
message: "I'm a final-year law student in Nairobi. I want a training contract at
a commercial firm next year, and I run 5k three mornings a week."
output:
{"facts": [{"scope":"shared","agent_id":null,"category":"education","key":"field_of_study","value":"law","confidence":0.95,"sensitive":false},
 {"scope":"shared","agent_id":null,"category":"education","key":"study_year","value":"final year","confidence":0.9,"sensitive":false},
 {"scope":"shared","agent_id":null,"category":"context","key":"location","value":"Nairobi","confidence":0.95,"sensitive":false},
 {"scope":"shared","agent_id":null,"category":"goals","key":"training_contract","value":"training contract at a commercial law firm, next year","confidence":0.9,"sensitive":false},
 {"scope":"agent","agent_id":"fitness","category":"routine","key":"running","value":"5k, three mornings a week","confidence":0.85,"sensitive":false}]%(example_tail)s}"""

_VALID_SCOPES = frozenset({"shared", "agent"})
#: Every specialist that can own a private note. "modeer" is included: Modeer
#: has its own namespace, so its private notes stay private rather than being
#: promoted to the shared layer every specialist reads.
_AGENT_SLUGS = frozenset(
    {
        "study",
        "career",
        "travel",
        "shopping",
        "finance",
        "fitness",
        "writing",
        "research",
        "email",
        "modeer",
    }
)
#: The categories the extraction prompt offers. Anything else is malformed:
#: category decides which specialists see a shared fact, so an unknown one is
#: not a harmless label.
_CATEGORIES = frozenset(
    {
        "education",
        "career",
        "goals",
        "context",
        "preferences",
        "health",
        "finance",
        "routine",
        "targets",
        "weak_topics",
        "general",
    }
)
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_VALUE = 300


_GOALS_SECTION = """

Goal changes — ONLY when the user explicitly asks, in this message, to add,
finish, pause, resume or re-rank a goal. Talking about a goal is not a request.
Their active goals, numbered:
%s
"goal_changes": a list, usually []. Each is one of
 {"op":"add","title":"<short>","priority":1-5 or null,"target_date":"YYYY-MM-DD" or null}
 {"op":"done"|"pause"|"resume","goal":<number>}
 {"op":"priority","goal":<number>,"priority":1-5}   (1 is the top priority)"""

_HANDOFF_SECTION = """

Handoff — ONLY when the user explicitly asks you to pass something to, brief or
tell a named teammate. Teammates: %s.
"handoff": null, or {"to":"<slug>","brief":"<one or two sentences for that
teammate: what the user wants from them and the details they gave>"}"""

_TRACKING_SECTION = """

Also, separately from facts:
"events": dated things ahead of the user that are worth following up — an
interview, exam, trip, deadline, race — whose day you can work out from today's
date (convert Hijri dates and religious holidays to the Gregorian date; if unsure,
leave the event out). [] if none. Each: {"title":"<short, e.g. Interview at
Stripe>","date":"YYYY-MM-DD","agent":"<slug of the teammate it fits, or null>",
"sensitive":true|false}.
"checkins": progress the user reports having done — a workout, a study session,
money spent, a task finished. [] if none. Each: {"agent":"fitness|study|finance|
career|writing|research|travel|shopping|email|modeer","text":"<short, e.g. ran
5k>","amount":<number or null>,"unit":"<e.g. km, min, pages, or null>",
"sensitive":true|false}. Do not put a currency in "unit" unless the user named one.
Never log food eaten, calories, fasting, skipped meals or body weight as check-ins.
sensitive=true for anything about health, injury, medical or therapy appointments,
bereavement, legal or family proceedings, or money trouble.
A check-in or event is not also a fact."""

_OUTCOMES_SECTION = """

The team recently asked how these went, numbered:
%s
"outcomes": [] unless the user says how one of them went. Each:
{"followup":<number>,"outcome":"<one short line in their words>"}"""

#: Words that can open a request to change goals. The model decides whether the
#: message really asks; without one of these it is not asked at all.
_GOAL_REQUEST = re.compile(
    r"\b(goals?|priorit\w*|mark\w*|done|finish\w*|complet\w*|pause\w*|resume\w*|"
    r"drop\w*|remove|add|track)\b",
    re.I,
)
_FIRST_PERSON = re.compile(r"\b(i|i'm|im|i've|i'd|i'll|me|my|mine|myself|we|we're|our|us)\b", re.I)
#: Signs a message mentions a date or reports something done, when nothing else
#: marks it as worth a look: "interview next Thursday", "ran 5k this morning".
_DATED_OR_DONE = re.compile(
    r"\b(today|tonight|tomorrow|yesterday|next (?:week|month|year|monday|tuesday|"
    r"wednesday|thursday|friday|saturday|sunday)|this (?:week|weekend|morning|evening)|"
    r"on (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|in \d+ (?:days|weeks)|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]* \d{1,2}|"
    r"\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|"
    r"ran|walked|swam|cycled|lifted|trained|studied|revised|spent|paid|bought|"
    r"finished|completed|applied|submitted|practised|practiced)\b",
    re.I,
)
_MAX_GOAL_CHANGES = 3
#: A pasted CV is long; the first part holds what matters.
_ABOUT_ME_CHARS = 8000
_MAX_BRIEF = 400
_MAX_EVENTS = 3
_MAX_CHECKINS = 5
#: How far ahead a follow-up may be. Further than this is a goal, not a date to
#: count down to.
_EVENT_HORIZON_DAYS = 400


@dataclass(slots=True)
class GoalChange:
    op: str  # add | done | pause | resume | priority
    title: str
    goal_id: str | None = None
    priority: int | None = None
    target_date: date | None = None
    applied: bool = False
    reason: str = ""


@dataclass(slots=True)
class Handoff:
    agent_id: str
    brief: str
    stored: bool = True
    reason: str = "passed on at your request"


@dataclass(slots=True)
class Event:
    """A dated thing ahead of the user, to follow up on."""

    agent_id: str
    title: str
    due_on: date
    stored: bool = True
    reason: str = "added to your follow-ups"
    id: str | None = None


@dataclass(slots=True)
class CheckInItem:
    agent_id: str
    text: str
    amount: float | None = None
    unit: str | None = None
    stored: bool = True
    reason: str = "logged"


@dataclass(slots=True)
class Outcome:
    """How a followed-up event went, in the user's words. Closes the follow-up."""

    followup_id: str
    title: str
    outcome: str | None


@dataclass(slots=True)
class TurnAnalysis:
    facts: list[Candidate] = field(default_factory=list)
    goal_changes: list[GoalChange] = field(default_factory=list)
    handoffs: list[Handoff] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    checkins: list[CheckInItem] = field(default_factory=list)
    outcomes: list[Outcome] = field(default_factory=list)


def teammate_names() -> dict[str, str]:
    """Lower-case teammate name -> agent slug."""
    from app.agents.registry import all_agents

    return {a.name.lower(): a.id for a in all_agents()}


#: Arabic spellings of the teammates' names, in folded form (see sensitivity._fold).
_ARABIC_NAMES = {
    "ليو": "modeer",
    "نوفا": "study",
    "هارفي": "career",
    "كلارا": "research",
    "اليكس": "writing",
    "تيسا": "travel",
    "نيت": "shopping",
    "ايما": "finance",
    "مادي": "fitness",
    "نورا": "email",
}
#: A request to pass something on: "tell Harvey", "ask Emma to", "let Nova know",
#: "قل لهارفي". The name must follow the verb closely; a name alone ("my friend
#: Alex said hi") is not a request, and Alex, Emma and Nora are common names.
_DIRECTIVE = re.compile(
    r"\b(?:tell|ask|let|brief|pass|send|forward|share|hand|update|remind|loop in|give)"
    r"\b(?:\s+(?:this|that|it|on|over|along)){0,2}(?:\s+(?:to|with))?\s+(\w+)",
    re.I,
)
_DIRECTIVE_AR = re.compile(r"(?:قل|قول|اسال|بلغ|اخبر|خبر|ابعت|ارسل|وصل)\s+(?:ل|الي\s+)?(\w+)")


def named_teammates(text: str, *, exclude: str) -> set[str]:
    """Slugs of the teammates the person asks to be told something, other than
    ``exclude``. A request, not a mention: see :data:`_DIRECTIVE`."""
    from app.memory.sensitivity import _fold

    names = teammate_names()
    found: set[str] = set()
    for match in _DIRECTIVE.finditer(text or ""):
        slug = names.get(match.group(1).lower())
        if slug:
            found.add(slug)
    for match in _DIRECTIVE_AR.finditer(_fold(text or "")):
        word = match.group(1)
        for name, slug in _ARABIC_NAMES.items():
            if word in (name, "ل" + name):
                found.add(slug)
    return found - {exclude}


def _mostly_non_latin(text: str) -> bool:
    """Written in another script, so the English patterns below cannot judge it.
    A few accented letters ("café", "Léo") do not count."""
    return sum(1 for ch in text if ch.isalpha() and not ch.isascii()) >= 3


#: First person and dated words in Arabizi (romanised Arabic) and French, which
#: are plain ASCII and so not caught by the script test.
_FIRST_PERSON_OTHER = re.compile(
    r"\b(ana|3andi|3ndi|b7eb|je|j'ai|j'|mon|ma|mes|moi)\b|\b(bokra|bukra|embare7|"
    r"demain|hier|la semaine prochaine)\b",
    re.I,
)


def worth_analyzing(
    text: str,
    *,
    previous_reply: str = "",
    agent_id: str,
    goals_allowed: bool,
    awaiting_answer: bool = False,
) -> bool:
    """Whether a message could hold a fact, a goal request or a handoff.

    Most turns are questions — "what's a good 3-day split?" — and asking a model
    to find facts in them spends a provider call to learn nothing. Errs towards
    asking: anything not plainly English, anything in the first person, and any
    answer to a question the agent just asked.
    """
    text = (text or "").strip()
    if len(text) < 6:
        return False
    if awaiting_answer:
        return True  # "It went well!" answers the question the team asked
    if _mostly_non_latin(text):
        return True  # the patterns below only know English
    if _FIRST_PERSON.search(text) or _FIRST_PERSON_OTHER.search(text):
        return True
    tail = (previous_reply or "")[-300:]
    if "?" in tail or "؟" in tail:
        return True
    if named_teammates(text, exclude=agent_id):
        return True
    if _DATED_OR_DONE.search(text):
        return True
    return goals_allowed and bool(_GOAL_REQUEST.search(text))


def _system_prompt(
    *, agent_id, today, known_keys, goals, handoffs, tracking=False, asked=None
) -> str:
    # The person's own keys first: cut alphabetically, the ones late in the
    # alphabet were dropped and then stored a second time under a new name.
    own = list(dict.fromkeys(known_keys))[:45]
    keys = own + [k for k in canonical_keys() if k not in own]
    dates = (
        f"\n- Today is {today:%A %d %B %Y}. Write dates in values as absolute dates "
        '("interview on Thu 1 Oct 2026", not "next Thursday"); if a date is '
        "unclear, keep the user's words."
        if today
        else ""
    )
    sections, extra_keys, tail = "", "", ""
    if tracking and today:
        sections += _TRACKING_SECTION
        extra_keys += ', "events": [...], "checkins": [...]'
        tail += ', "events": [], "checkins": []'
    if asked:
        listed = "\n".join(f"{i}. {f.title}" for i, f in enumerate(asked, 1))
        sections += _OUTCOMES_SECTION % listed
        extra_keys += ', "outcomes": [...]'
        tail += ', "outcomes": []'
    if goals is not None:
        listed = "\n".join(f"{i}. {g.title}" for i, g in enumerate(goals, 1)) or "(none)"
        sections += _GOALS_SECTION % listed
        extra_keys += ', "goal_changes": [...]'
        tail += ', "goal_changes": []'
    if handoffs:
        from app.agents.registry import all_agents

        team = ", ".join(f"{a.name}={a.id}" for a in all_agents() if a.id != agent_id)
        sections += _HANDOFF_SECTION % team
        extra_keys += ', "handoff": null'
        tail += ', "handoff": null'
    return _SYSTEM % {
        "extra_keys": extra_keys,
        "keys": ", ".join(keys),
        "dates": dates,
        "sections": sections,
        "example_tail": tail,
    }


async def analyze_turn(
    text: str,
    *,
    agent_id: str,
    provider: LLMProvider,
    model: str,
    today: date | None = None,
    known_keys: tuple[str, ...] | list[str] = (),
    goals: list | None = None,
    learn_facts: bool = True,
    about_me: bool = False,
    asked: list | None = None,
) -> TurnAnalysis:
    """One call for everything a message can ask the team to remember or do.

    ``goals`` is the active goal list, passed only for Leo: only he may change
    goals. ``learn_facts=False`` (automatic memory off) keeps the explicit
    requests and drops every fact, follow-up and check-in. Pasted text is
    removed first, so nothing in it is saved as being about the user — unless
    the person said the text is about them (``about_me``, or a message that
    opens "This is about me:" / "Here's my CV:").

    With ``today`` the same call also picks up dated events (follow-ups) and
    reported progress (check-ins). ``asked`` is the follow-ups the team has
    asked about and is waiting to hear on; an answer closes them.
    """
    text = (text or "").strip()
    about_me = about_me or is_about_me(text)
    if not about_me:
        text, _ = strip_pasted(text)
    if len(text) < 6:
        return TurnAnalysis()
    handoffs = bool(named_teammates(text, exclude=agent_id))
    goals_allowed = goals is not None and (
        bool(_GOAL_REQUEST.search(text)) or _mostly_non_latin(text)
    )
    asked = asked if learn_facts and not about_me else None
    if not learn_facts and not handoffs and not goals_allowed:
        return TurnAnalysis()

    try:
        result = await provider.complete(
            system=_system_prompt(
                agent_id=agent_id,
                today=today,
                known_keys=known_keys,
                goals=goals if goals_allowed else None,
                handoffs=handoffs,
                tracking=learn_facts and not about_me,
                asked=asked,
            ),
            messages=[
                LLMMessage(role="user", content=text[: _ABOUT_ME_CHARS if about_me else None])
            ],
            model=model,
            temperature=0.0,
            # A CV holds many facts at once.
            max_tokens=1000 if about_me else 650,
        )
        raw = _parse_json(result.text)
    except Exception:  # noqa: BLE001 - never let extraction break a turn
        facts = extract_candidates(text, agent_id=agent_id) if learn_facts else []
        return TurnAnalysis(facts=facts)

    analysis = TurnAnalysis()
    if learn_facts:
        seen: set[tuple[str, str]] = set()
        for item in raw.get("facts") or []:
            cand = _to_candidate(item, agent_id=agent_id) if isinstance(item, dict) else None
            if cand is None:
                continue
            dedupe = (cand.key, cand.value.lower())
            if dedupe in seen:
                continue
            seen.add(dedupe)
            analysis.facts.append(cand)
    if learn_facts and today and not about_me:
        analysis.events = _to_events(raw.get("events"), agent_id=agent_id, today=today)
        analysis.checkins = _to_checkins(raw.get("checkins"), agent_id=agent_id)
    if asked:
        analysis.outcomes = _to_outcomes(raw.get("outcomes"), asked)
    if goals_allowed:
        analysis.goal_changes = _to_goal_changes(raw.get("goal_changes"), goals or [])
    if handoffs:
        handoff = _to_handoff(raw.get("handoff"), agent_id=agent_id, text=text)
        if handoff is not None:
            analysis.handoffs.append(handoff)
    return analysis


async def llm_extract_candidates(
    text: str,
    *,
    agent_id: str,
    provider: LLMProvider,
    model: str,
) -> list[Candidate]:
    """Facts only: :func:`analyze_turn` without goals, dates or known keys."""
    analysis = await analyze_turn(text, agent_id=agent_id, provider=provider, model=model)
    return analysis.facts


def _parse_json(text: str) -> dict:
    """The model's answer as {"facts": [...], ...}.

    Accepts the older bare array of facts too, and JSON wrapped in prose or a
    code fence. Anything else raises, which means "fall back to the rules".
    """
    text = text.strip().strip("`")
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("no JSON in response")
    start = min(starts)
    if text[start] == "[":
        end = text.rfind("]")
        if end < start:
            raise ValueError("no JSON array in response")
        data = json.loads(text[start : end + 1])
        return {"facts": [d for d in data if isinstance(d, dict)]}
    end = text.rfind("}")
    if end < start:
        raise ValueError("no JSON object in response")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict) or not isinstance(data.get("facts", []), list):
        raise ValueError("malformed analysis")
    return data


def _to_goal_changes(raw, goals: list) -> list[GoalChange]:
    """Validate proposed goal changes. Anything malformed is dropped, not repaired."""
    if not isinstance(raw, list):
        return []
    out: list[GoalChange] = []
    for item in raw[:_MAX_GOAL_CHANGES]:
        if not isinstance(item, dict):
            continue
        op = item.get("op")
        priority = item.get("priority")
        if priority is not None and (
            isinstance(priority, bool) or not isinstance(priority, int) or not 1 <= priority <= 5
        ):
            continue
        if op == "add":
            title = item.get("title")
            if not isinstance(title, str) or not 2 <= len(title.strip()) <= 200:
                continue
            target = None
            if isinstance(item.get("target_date"), str):
                try:
                    target = date.fromisoformat(item["target_date"])
                except ValueError:
                    target = None
            out.append(GoalChange("add", title.strip(), priority=priority, target_date=target))
            continue
        number = item.get("goal")
        if op not in ("done", "pause", "resume", "priority"):
            continue
        if isinstance(number, bool) or not isinstance(number, int):
            continue
        if not 1 <= number <= len(goals):
            continue
        if op == "priority" and priority is None:
            continue
        goal = goals[number - 1]
        out.append(GoalChange(op, goal.title, goal_id=goal.id, priority=priority))
    return out


def _slug_or(raw, default: str) -> str:
    if isinstance(raw, str) and raw.strip().lower() in _AGENT_SLUGS:
        return raw.strip().lower()
    return default


def _to_events(raw, *, agent_id: str, today: date) -> list[Event]:
    if not isinstance(raw, list):
        return []
    out: list[Event] = []
    for item in raw[:_MAX_EVENTS]:
        if not isinstance(item, dict):
            continue
        title, when = item.get("title"), item.get("date")
        if not isinstance(title, str) or not isinstance(when, str):
            continue
        title = " ".join(title.split())
        try:
            due = date.fromisoformat(when.strip())
        except ValueError:
            continue
        if not 3 <= len(title) <= 200:
            continue
        if not 0 <= (due - today).days <= _EVENT_HORIZON_DAYS:
            continue  # a date in the past is not something to follow up on
        event = Event(_slug_or(item.get("agent"), agent_id), title, due)
        # Fail closed, as for facts: the model's flag counts only when it is a
        # real False, and the keyword backstop can raise it but never lower it.
        flagged = item.get("sensitive") is not False or looks_sensitive(title)
        if flagged and not settings.memory_store_sensitive:
            event.stored, event.reason = False, "sensitive; not stored automatically"
        out.append(event)
    return out


def _to_checkins(raw, *, agent_id: str) -> list[CheckInItem]:
    if not isinstance(raw, list):
        return []
    out: list[CheckInItem] = []
    for item in raw[:_MAX_CHECKINS]:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not 2 <= len(text.strip()) <= 200:
            continue
        amount = item.get("amount")
        if (
            isinstance(amount, bool)
            or not isinstance(amount, int | float)
            or not -1e9 < amount < 1e9
        ):
            amount = None
        unit = item.get("unit")
        unit = unit.strip()[:24] if isinstance(unit, str) and unit.strip() else None
        entry = CheckInItem(
            _slug_or(item.get("agent"), agent_id),
            " ".join(text.split()),
            float(amount) if amount is not None else None,
            unit,
        )
        flagged = item.get("sensitive") is not False or looks_sensitive(entry.text)
        if flagged and not settings.memory_store_sensitive:
            entry.stored, entry.reason = False, "sensitive; not stored automatically"
        out.append(entry)
    return out


def _to_outcomes(raw, asked: list) -> list[Outcome]:
    if not isinstance(raw, list):
        return []
    out: list[Outcome] = []
    for item in raw[: len(asked)]:
        if not isinstance(item, dict):
            continue
        number = item.get("followup")
        if isinstance(number, bool) or not isinstance(number, int):
            continue
        if not 1 <= number <= len(asked):
            continue
        followup = asked[number - 1]
        text = item.get("outcome")
        text = " ".join(text.split())[:200] if isinstance(text, str) else None
        if text and looks_sensitive(text) and not settings.memory_store_sensitive:
            text = None  # closed, but the words are not kept
        out.append(Outcome(followup.id, followup.title, text or None))
    return out


def _to_handoff(raw, *, agent_id: str, text: str) -> Handoff | None:
    if not isinstance(raw, dict):
        return None
    to, brief = raw.get("to"), raw.get("brief")
    if not isinstance(to, str) or not isinstance(brief, str):
        return None
    to = to.strip().lower()
    brief = " ".join(brief.split())
    # Only to a teammate the person actually named, and never to oneself.
    if to not in named_teammates(text, exclude=agent_id):
        return None
    if not 10 <= len(brief) <= _MAX_BRIEF:
        return None
    if (
        looks_sensitive("handoff", brief, category="handoff")
        and not settings.memory_store_sensitive
    ):
        return Handoff(to, brief, stored=False, reason="sensitive; not passed on automatically")
    return Handoff(to, brief)


def _to_candidate(item: dict, *, agent_id: str) -> Candidate | None:
    """Validate one model-proposed fact. Anything malformed is rejected outright.

    This used to repair bad output instead: an unknown scope became "shared", a
    private note for a misspelt or unknown specialist was PROMOTED to the shared
    layer every specialist reads, and a non-numeric confidence defaulted to a
    value that passed the storage threshold. Every one of those failed open.
    Now nothing is guessed — a candidate is either well-formed or dropped, and a
    private note is never widened into a shared one.
    """
    scope = item.get("scope")
    key = item.get("key")
    value = item.get("value")
    category = item.get("category")
    confidence = item.get("confidence")
    raw_agent = item.get("agent_id")

    # Every field must be present and of the right type. No defaults: a default
    # is a guess, and a guessed scope or confidence is how facts leaked before.
    if not all(isinstance(field, str) for field in (scope, key, value, category)):
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, int | float):
        return None

    scope = scope.strip().lower()
    key = key.strip().lower().replace(" ", "_")
    value = value.strip().rstrip(".").strip()
    category = category.strip().lower()

    if scope not in _VALID_SCOPES or category not in _CATEGORIES:
        return None
    if not _KEY.match(key) or not 2 <= len(value) <= _MAX_VALUE:
        return None
    if not 0.0 <= float(confidence) <= 1.0:
        return None

    target_agent: str | None = None
    if scope == "agent":
        if not isinstance(raw_agent, str):
            return None
        target_agent = raw_agent.strip().lower()
        if target_agent not in _AGENT_SLUGS:
            # A private note for a specialist we do not know. It is NOT
            # widened to shared: better lost than overheard by the whole team.
            return None
        if agent_id not in (target_agent, "modeer"):
            # Only capture a specialist's private fact in that specialist's
            # chat, or with Modeer, who briefs the whole team.
            return None
    elif raw_agent not in (None, ""):
        # "shared" but naming a specialist is contradictory, and the private
        # reading is the one that must win.
        return None

    confidence = round(float(confidence), 2)
    # The model's flag counts only when it is a real boolean; anything else is
    # treated as sensitive. The keyword backstop can raise the flag but never
    # lower it.
    flagged = item.get("sensitive")
    sensitive = flagged is not False or looks_sensitive(key, value, category=category)

    if sensitive and not settings.memory_store_sensitive:
        return Candidate(
            scope,
            target_agent,
            category,
            key,
            value,
            confidence,
            True,
            False,
            "sensitive; not stored automatically",
        )
    if confidence < settings.memory_min_confidence:
        return Candidate(
            scope,
            target_agent,
            category,
            key,
            value,
            confidence,
            sensitive,
            False,
            "confidence below threshold",
        )
    return Candidate(
        scope,
        target_agent,
        category,
        key,
        value,
        confidence,
        sensitive,
        True,
        "durable personal fact",
    )
