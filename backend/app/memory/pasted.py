"""Remove pasted and quoted text before learning from a message.

People paste other people's words: an email they want to answer, a job advert,
a message from a friend. "I'm based in Berlin" in a recruiter's email is a fact
about the recruiter. Only what the person wrote themselves is learned from, so
pasted blocks are cut out before extraction and replaced with a marker.

Deliberately conservative in what it keeps: when a block might be pasted, it is
dropped. Missing one fact costs little; saving a stranger's details as the
user's own is exactly the failure this exists to prevent.
"""

from __future__ import annotations

import re

MARKER = "[pasted text omitted]"

#: The person saying the text that follows is about them: a CV, a bio, a profile.
_ABOUT_ME = re.compile(
    r"^\s*(?:this is (?:about me|my (?:cv|resume|résumé|bio|profile))"
    r"|here(?:'s| is) (?:my (?:cv|resume|résumé|bio|profile|linkedin(?: profile)?)|about me)"
    r"|about me"
    # French and Arabic: "voici mon CV", "à propos de moi", "هذه سيرتي الذاتية", "عني"
    r"|voici mon (?:cv|profil)|(?:à|a) propos de moi"
    r"|(?:هذه|هذي|دي)\s+سيرتي(?:\s+الذاتية)?|هذا\s+ملفي|نبذة\s+عني|عني)\s*[:：\-—]",
    re.I,
)
#: Invisible direction marks that mail clients put before ">" and headers; "\s"
#: does not match them, so they hid quoted lines from the patterns below.
_BIDI = re.compile("[\u200e\u200f\u061c\u202a-\u202e\u2066-\u2069]")


def _plain(text: str) -> str:
    """Curly apostrophes straightened and direction marks removed."""
    return _BIDI.sub("", (text or "").replace("\u2019", "'").replace("\u02bc", "'"))


def is_about_me(text: str) -> bool:
    """Whether the message opens by saying the text is about the person."""
    return bool(_ABOUT_ME.match(_plain(text)))


_FENCE = re.compile(r"```.*?(?:```|\Z)", re.S)
#: Email header lines, in English, French and Arabic (Gmail and Outlook labels).
_HEADER = re.compile(
    r"^\s*(from|to|cc|bcc|subject|sent|date|reply-to"
    r"|de|à|a|objet|envoyé|répondre à"
    r"|من|إلى|الى|نسخة|نسخة مخفية|الموضوع|التاريخ|تاريخ الإرسال|أرسلت|ارسلت|رد إلى)\s*[:：]",
    re.I | re.M,
)
_FORWARD = re.compile(
    r"^\s*(-{2,}\s*(original|forwarded) message\s*-{2,}"
    r"|begin forwarded message:?"
    r"|on .{3,80} wrote:\s*$"
    r"|-{2,}\s*message (?:transféré|d'origine)\s*-{2,}|le .{3,80} a écrit\s*:\s*$"
    r"|-{2,}\s*(?:رسالة (?:معاد توجيهها|مُعاد توجيهها|محولة|أصلية))\s*-{2,}"
    r"|في .{3,80} كتب\s*[:：]\s*$)",
    re.I | re.M,
)
#: A paragraph introducing what follows: "Here's the email she sent:".
_INTRO = re.compile(r"[:：]\s*$")
#: The person speaking again after a paste: short, and asking or saying
#: something about themselves.
_OWN_VOICE = re.compile(
    r"[?؟]|\b(can you|could you|please|help me|what should|how do i|i\b|i'm|i am|my\b"
    r"|peux-tu|pouvez-vous|aide-moi|je\b|mon\b)"
    r"|ساعدني|كيف|شو|ايش|إيش|ممكن|أرد|ارد|أنا|انا",
    re.I,
)
#: A paste long enough to be someone else's text rather than a quick example.
_LONG = 200
_SHORT_ASK = 280


def strip_pasted(text: str) -> tuple[str, bool]:
    """``text`` with pasted blocks replaced by a marker, and whether any were."""
    original = text or ""
    text = _FENCE.sub(f"\n\n{MARKER}\n\n", _plain(original))
    paragraphs = re.split(r"\n\s*\n", text)
    kept: list[str] = []
    pasting = False
    pasted = 0  # paragraphs dropped since the paste began
    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped:
            continue
        if stripped == MARKER:
            _mark(kept)
            continue
        rest = "\n\n".join(paragraphs[i + 1 :]).strip()
        starts_paste = (
            len(_HEADER.findall(stripped)) >= 2
            or bool(_FORWARD.search(stripped))
            or _all_quoted(stripped)
        )
        # A paste is at least one paragraph: the one right after "She wrote:"
        # is theirs however much it sounds like the user.
        if pasting and pasted and _is_closing_ask(stripped, rest):
            pasting = False
        elif starts_paste:
            pasting = True
        if pasting:
            pasted += 1
            _mark(kept)
            continue
        kept.append(_drop_quoted_lines(stripped))
        # "Here is what my landlord sent:" followed by a long block: the block
        # is theirs, not the user's.
        if _INTRO.search(stripped) and len(rest) >= _LONG:
            pasting, pasted = True, 0
    cleaned = "\n\n".join(p for p in kept if p.strip())
    return cleaned, MARKER in cleaned


def _mark(kept: list[str]) -> None:
    if not kept or kept[-1] != MARKER:
        kept.append(MARKER)


def _all_quoted(paragraph: str) -> bool:
    lines = [ln for ln in paragraph.splitlines() if ln.strip()]
    return bool(lines) and all(ln.lstrip().startswith(">") for ln in lines)


def _drop_quoted_lines(paragraph: str) -> str:
    lines = paragraph.splitlines()
    if not any(ln.lstrip().startswith(">") for ln in lines):
        return paragraph
    out: list[str] = []
    for ln in lines:
        if ln.lstrip().startswith(">"):
            if not out or out[-1] != MARKER:
                out.append(MARKER)
        else:
            out.append(ln)
    return "\n".join(out)


def _is_closing_ask(paragraph: str, rest: str) -> bool:
    """The last paragraph after a paste, when it is the person asking for help."""
    return (
        not rest
        and len(paragraph) <= _SHORT_ASK
        and not _HEADER.search(paragraph)
        and bool(_OWN_VOICE.search(paragraph))
    )
