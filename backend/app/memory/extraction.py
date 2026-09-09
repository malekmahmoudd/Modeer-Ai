"""Candidate memory extraction.

Deterministic and rule-based on purpose: memory writes must be predictable and
testable, and the MVP explicitly avoids tool/LLM-driven autonomy. The classifier
separates four cases the brief calls out:

  * temporary details          -> never stored
  * durable shared information  -> shared personal context
  * useful specialist info      -> that agent's namespace
  * should-not-be-stored        -> sensitive; dropped unless the user opts in
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings

SHARED = "shared"
AGENT = "agent"


@dataclass(slots=True)
class Candidate:
    scope: str  # "shared" | "agent"
    agent_id: str | None
    category: str
    key: str
    value: str
    confidence: float
    sensitive: bool
    stored: bool
    reason: str


# --- signals -----------------------------------------------------------------

_TEMPORARY = re.compile(
    r"\b(today|tonight|right now|this morning|this afternoon|tomorrow|yesterday|"
    r"this week i (?:feel|am feeling)|currently sitting|just woke|so tired|"
    r"good morning|good evening|thanks|thank you|hello|hi there)\b",
    re.IGNORECASE,
)

_SENSITIVE = re.compile(
    r"\b(diagnos(?:ed|is)|depression|anxiety|hiv|cancer|medication|prescrib|"
    r"therapy|salary is|i earn|i make \$?\d|net worth|password|passport number|"
    r"social security|ssn|credit card|bank account|religion|pregnan|disabilit)\b",
    re.IGNORECASE,
)

_HEDGE = re.compile(r"\b(maybe|i think|i guess|probably|might|not sure|kind of)\b", re.I)

# pattern -> (scope, agent_id, category, key)
_RULES: list[tuple[re.Pattern[str], str, str | None, str, str]] = [
    (re.compile(r"\bi(?:'m| am) (?:currently )?studying ([^.,;\n]{2,80})", re.I),
     SHARED, None, "education", "field_of_study"),
    (re.compile(r"\bmy major is ([^.,;\n]{2,80})", re.I),
     SHARED, None, "education", "major"),
    (re.compile(r"\bi(?:'m| am) (?:a|an) ([a-z ]{3,40}?) (?:student|undergrad|"
                r"graduate student|phd candidate)\b", re.I),
     SHARED, None, "education", "level"),
    (re.compile(r"\bi study at ([^.,;\n]{2,80})", re.I),
     SHARED, None, "education", "institution"),
    (re.compile(r"\bi(?:'m| am) (?:a|an) ([a-z /]{3,40}?) (?:by profession|"
                r"for a living|at [A-Z])", re.I),
     SHARED, None, "career", "current_role"),
    (re.compile(r"\bi work as (?:a|an) ([^.,;\n]{2,60})", re.I),
     SHARED, None, "career", "current_role"),
    (re.compile(r"\bi want to (?:become|be) (?:a|an)? ?([^.,;\n]{2,60})", re.I),
     SHARED, None, "career", "career_goal"),
    (re.compile(r"\bmy (?:career )?goal is (?:to )?([^.,;\n]{2,120})", re.I),
     SHARED, None, "goals", "stated_goal"),
    (re.compile(r"\bi(?:'m| am) preparing for (?:a|an|my)? ?([^.,;\n]{2,80})", re.I),
     SHARED, None, "goals", "preparing_for"),
    (re.compile(r"\bi live in ([^.,;\n]{2,60})", re.I),
     SHARED, None, "context", "location"),
    (re.compile(r"\bi(?:'m| am) based in ([^.,;\n]{2,60})", re.I),
     SHARED, None, "context", "location"),
    (re.compile(r"\bi(?:'m| am) from ([^.,;\n]{2,60})", re.I),
     SHARED, None, "context", "home_country"),
    (re.compile(r"\bmy native language is ([^.,;\n]{2,40})", re.I),
     SHARED, None, "context", "native_language"),
    (re.compile(r"\bi(?:'m| am) (\d{2}) years old\b", re.I),
     SHARED, None, "context", "age"),
    # sensitive: matched so they can be *flagged and dropped*, not stored
    (re.compile(r"\b(?:i was |i've been |been )?diagnosed with ([^.,;\n]{2,60})", re.I),
     SHARED, None, "health", "condition"),
    (re.compile(r"\bmy salary is ([^.,;\n]{2,40})", re.I),
     SHARED, None, "finance", "salary"),
    (re.compile(r"\bi (?:earn|make) (\$?\d[\d,.]{2,})", re.I),
     SHARED, None, "finance", "income"),
    # specialist-scoped
    (re.compile(r"\bi(?:'m| am) weak (?:at|in) ([^.,;\n]{2,60})", re.I),
     AGENT, "study", "weak_topics", "weak_topic"),
    (re.compile(r"\bi struggle with ([^.,;\n]{2,60})", re.I),
     AGENT, "study", "weak_topics", "struggle"),
    (re.compile(r"\bi learn best (?:by|with|through) ([^.,;\n]{2,60})", re.I),
     AGENT, "study", "preferences", "learning_style"),
    (re.compile(r"\bi prefer (?:to travel|travelling|traveling) ([^.,;\n]{2,60})", re.I),
     AGENT, "travel", "preferences", "travel_style"),
    (re.compile(r"\bmy budget is ([^.,;\n]{2,40})", re.I),
     AGENT, "shopping", "preferences", "budget"),
    (re.compile(r"\bi work out ([^.,;\n]{2,60})", re.I),
     AGENT, "fitness", "routine", "workout_frequency"),
    (re.compile(r"\bmy target role is ([^.,;\n]{2,60})", re.I),
     AGENT, "career", "targets", "target_role"),
]


def _confidence(text: str, base: float) -> float:
    return round(base * (0.65 if _HEDGE.search(text) else 1.0), 2)


# Trailing-clause boundaries: keep the noun phrase, drop the rest of the sentence.
_CLIP = re.compile(
    r"\s+(?:,|;|—|-|\band\b|\bbut\b|\bso\b|\bbecause\b|\bwhich\b|\bwhile\b|"
    r"\bright now\b|\bat\b|\band i\b|\band i'm\b)\b.*$",
    re.IGNORECASE,
)
_TRAILING_FILLER = re.compile(r"\b(?:the|a|an|my|at|for|and|to)$", re.IGNORECASE)


def _clip(value: str) -> str:
    value = _CLIP.sub("", value).strip().rstrip(".,;").strip()
    value = _TRAILING_FILLER.sub("", value).strip()
    return value


def extract_candidates(text: str, *, agent_id: str) -> list[Candidate]:
    text = (text or "").strip()
    if not text or len(text) < 6:
        return []

    out: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    is_temporary = bool(_TEMPORARY.search(text)) and len(text) < 140

    for pattern, scope, rule_agent, category, key in _RULES:
        m = pattern.search(text)
        if not m:
            continue
        value = _clip(m.group(1).strip())
        if len(value) < 2:
            continue
        dedupe = (key, value.lower())
        if dedupe in seen:
            continue
        seen.add(dedupe)

        target_agent = rule_agent if scope == AGENT else None
        # Agent-scoped rules only fire inside their own agent's chat, or from Modeer.
        if scope == AGENT and agent_id not in (rule_agent, "modeer"):
            continue

        sensitive = bool(_SENSITIVE.search(m.group(0)) or _SENSITIVE.search(text))
        base_conf = 0.8
        confidence = _confidence(text, base_conf)

        if is_temporary:
            out.append(Candidate(scope, target_agent, category, key, value,
                                  confidence, sensitive, False,
                                  "looks like a transient detail"))
            continue
        if sensitive and not settings.memory_store_sensitive:
            out.append(Candidate(scope, target_agent, category, key, value,
                                 confidence, True, False,
                                 "sensitive; not stored automatically"))
            continue
        if confidence < settings.memory_min_confidence:
            out.append(Candidate(scope, target_agent, category, key, value,
                                 confidence, sensitive, False,
                                 "confidence below threshold"))
            continue
        out.append(Candidate(scope, target_agent, category, key, value,
                             confidence, sensitive, True, "durable personal fact"))
    return out
