"""A CV as a Word file, written directly: a .docx is a zip of a few XML parts,
so no document library is needed for plain headings, lines and bullets."""

from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape

from app.cv.schemas import CvData

_ARABIC = re.compile(r"[؀-ۿ]")

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml"
 ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Target="word/document.xml"
 Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>
</Relationships>"""

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

HEADINGS = {
    "en": {
        "summary": "Summary",
        "experience": "Experience",
        "education": "Education",
        "skills": "Skills",
        "languages": "Languages",
    },
    "ar": {
        "summary": "نبذة",
        "experience": "الخبرة",
        "education": "التعليم",
        "skills": "المهارات",
        "languages": "اللغات",
    },
}


def _para(
    text: str,
    *,
    size: int = 21,
    bold: bool = False,
    bullet: bool = False,
    rtl: bool = False,
    space_before: int = 0,
    colour: str | None = None,
) -> str:
    if not text:
        return ""
    ppr = []
    if rtl:
        ppr.append("<w:bidi/>")
    ppr.append(f'<w:spacing w:before="{space_before}" w:after="60"/>')
    if bullet:
        ppr.append('<w:ind w:left="360" w:hanging="220"/>')
        text = "• " + text
    rpr = [f'<w:sz w:val="{size}"/>']
    if bold:
        rpr.insert(0, "<w:b/>")
    if colour:
        rpr.append(f'<w:color w:val="{colour}"/>')
    if rtl:
        rpr.append("<w:rtl/>")
    return (
        f"<w:p><w:pPr>{''.join(ppr)}</w:pPr><w:r><w:rPr>{''.join(rpr)}</w:rPr>"
        f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'
    )


def _join(*parts: str, sep: str = " · ") -> str:
    return sep.join(p for p in parts if p)


def render(cv: CvData) -> bytes:
    """The .docx bytes for one CV. Arabic text runs right to left."""
    rtl = bool(_ARABIC.search(cv.name + cv.headline + cv.summary))
    words = HEADINGS["ar" if rtl else "en"]

    def heading(key: str) -> str:
        return _para(words[key], size=24, bold=True, rtl=rtl, space_before=240, colour="1F3A5F")

    body = [
        _para(cv.name, size=36, bold=True, rtl=rtl),
        _para(cv.headline, size=24, rtl=rtl, colour="444444"),
        _para(_join(cv.email, cv.phone, cv.location, *cv.links), size=19, rtl=rtl),
    ]
    if cv.summary:
        body += [heading("summary"), _para(cv.summary, rtl=rtl)]
    if cv.experience:
        body.append(heading("experience"))
        for role in cv.experience:
            dates = _join(role.start, role.end, sep=" – ")
            body.append(
                _para(
                    _join(role.title, role.organisation, role.place),
                    bold=True,
                    rtl=rtl,
                    space_before=120,
                )
            )
            body.append(_para(dates, size=19, rtl=rtl, colour="666666"))
            body += [_para(b, bullet=True, rtl=rtl) for b in role.bullets]
    if cv.education:
        body.append(heading("education"))
        for study in cv.education:
            body.append(
                _para(
                    _join(study.qualification, study.institution),
                    bold=True,
                    rtl=rtl,
                    space_before=120,
                )
            )
            body.append(
                _para(_join(study.start, study.end, sep=" – "), size=19, rtl=rtl, colour="666666")
            )
            body.append(_para(study.note, rtl=rtl))
    if cv.skills:
        body += [heading("skills"), _para(", ".join(cv.skills), rtl=rtl)]
    if cv.languages:
        body += [heading("languages"), _para(", ".join(cv.languages), rtl=rtl)]

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}"><w:body>{"".join(body)}'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1000" w:right="1000" w:bottom="1000" w:left="1000"'
        ' w:header="0" w:footer="0" w:gutter="0"/></w:sectPr></w:body></w:document>'
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", document)
    return out.getvalue()
