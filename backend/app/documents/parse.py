"""Turn an uploaded file into plain text, safely.

Parsers for PDF and DOCX have a long record of crashes and hangs on hostile
files, so parsing never happens in the server process. :func:`parse_isolated`
runs this module as a child process with limits on CPU time, memory and wall
time; whatever it returns is JSON text, and a crash or a hang there costs one
failed upload, not the server.

The file type comes from the bytes, never from the name or the Content-Type.
DOCX is read with the standard library (it is a zip of XML): no document
library, and entity declarations are refused outright.
"""

from __future__ import annotations

import asyncio
import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

KINDS = ("pdf", "docx", "txt", "md", "image")
#: A PDF page with less text than this is treated as scanned and read with OCR.
_SCANNED_PAGE_CHARS = 20
_MAX_PAGES = 500
# Zip-bomb guards for DOCX: entries, total unpacked size, and the ratio.
_ZIP_MAX_ENTRIES = 2000
_ZIP_MAX_UNPACKED = 100 * 1024 * 1024
_ZIP_MAX_RATIO = 100
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class Unsupported(ValueError):
    """The file is not something we can read; the message is safe to show."""


@dataclass(slots=True)
class Page:
    number: int | None  # None for formats without pages
    text: str
    ocr: bool = False  # read from an image, so words may be wrong


def detect_kind(data: bytes, filename: str) -> str:
    """The file's real type, from its bytes. Raises :class:`Unsupported`."""
    head = data[:1024]
    if b"%PDF-" in head:
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        if filename.lower().endswith(".docx"):
            return "docx"
        raise Unsupported("Only .docx is accepted of the zip-based formats.")
    if head.startswith((b"\x89PNG", b"\xff\xd8\xff")) or (
        head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    ):
        return "image"
    if head.startswith((b"GIF8", b"RIFF")) or head[4:12] in (b"ftypheic", b"ftypmif1"):
        raise Unsupported("That image format isn't supported. Use a JPEG, PNG or WebP photo.")
    if b"\x00" in data[:8192] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise Unsupported("That looks like a binary file. Upload a PDF, DOCX, TXT, MD or a photo.")
    return "md" if filename.lower().endswith((".md", ".markdown")) else "txt"


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise Unsupported("The text file isn't UTF-8. Save it as UTF-8 and try again.")


def _pdf(data: bytes) -> list[Page]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise Unsupported("The PDF is password-protected.")
        pages = []
        for number, page in enumerate(reader.pages[:_MAX_PAGES], 1):
            pages.append(Page(number, page.extract_text() or ""))
        return pages
    except Unsupported:
        raise
    except Exception as exc:  # noqa: BLE001 - any parser error is "unreadable"
        raise Unsupported("The PDF could not be read.") from exc


def _docx(data: bytes) -> list[Page]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise Unsupported("The DOCX file is damaged.") from exc
    infos = archive.infolist()
    unpacked = sum(i.file_size for i in infos)
    packed = max(1, sum(i.compress_size for i in infos))
    if (
        len(infos) > _ZIP_MAX_ENTRIES
        or unpacked > _ZIP_MAX_UNPACKED
        or unpacked / packed > _ZIP_MAX_RATIO
    ):
        raise Unsupported("The DOCX file is too large once unpacked.")
    try:
        xml = archive.read("word/document.xml")
    except KeyError as exc:
        raise Unsupported("That zip file is not a Word document.") from exc
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise Unsupported("The DOCX file contains declarations we don't accept.")
    root = ElementTree.fromstring(xml)
    body = root.find(f"{_W}body")
    lines: list[str] = []
    for block in list(body) if body is not None else []:
        if block.tag == f"{_W}p":
            lines.append(_paragraph(block))
        elif block.tag == f"{_W}tbl":
            for row in block.iter(f"{_W}tr"):
                cells = [
                    " ".join(_paragraph(p) for p in cell.iter(f"{_W}p")).strip()
                    for cell in row.iter(f"{_W}tc")
                ]
                lines.append(" | ".join(c for c in cells if c))
    return [Page(None, "\n\n".join(line for line in lines if line.strip()))]


def _paragraph(p) -> str:
    parts: list[str] = []
    for node in p.iter():
        if node.tag == f"{_W}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{_W}tab":
            parts.append("\t")
        elif node.tag in (f"{_W}br", f"{_W}cr"):
            parts.append("\n")
    text = "".join(parts).strip()
    style = p.find(f"{_W}pPr/{_W}pStyle")
    name = (style.get(f"{_W}val") or "") if style is not None else ""
    if text and name.lower().startswith(("heading", "title")):
        return "# " + text  # headings travel as Markdown, like .md files
    return text


def _image(data: bytes) -> list[Page]:
    from app.documents import ocr

    if not ocr.available():
        raise Unsupported("Reading text from photos isn't set up on this server.")
    try:
        image = ocr.open_image(data)
    except Exception as exc:  # noqa: BLE001 - damaged, truncated or a bomb
        raise Unsupported("The image could not be opened.") from exc
    return [Page(None, ocr.read_image(ocr.prepare(image)), ocr=True)]


def _ocr_scanned(data: bytes, pages: list[Page]) -> list[Page]:
    """Read the pages of a PDF that have no text layer, if OCR is available."""
    from app.documents import ocr

    scanned = [p.number for p in pages if len(p.text.strip()) < _SCANNED_PAGE_CHARS]
    if not scanned or not ocr.available():
        return pages
    by_number = {p.number: p for p in pages}
    try:
        for number, image in ocr.pdf_pages(data, scanned[: ocr.MAX_OCR_PAGES]):
            by_number[number] = Page(number, ocr.read_image(ocr.prepare(image)), ocr=True)
    except Exception:  # noqa: BLE001 - keep whatever text the PDF did have
        pass
    return [by_number[p.number] for p in pages]


def parse(data: bytes, kind: str) -> list[Page]:
    """Pages of text. Raises :class:`Unsupported` with a message for the user."""
    if kind == "pdf":
        pages = _ocr_scanned(data, _pdf(data))
    elif kind == "image":
        pages = _image(data)
    elif kind == "docx":
        pages = _docx(data)
    else:
        pages = [Page(None, _decode(data))]
    for page in pages:
        page.text = _tidy(page.text)
    return pages


def _tidy(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --- isolation -----------------------------------------------------------------------


_CHILD_MEMORY = 768 * 1024 * 1024


def _limit_child() -> None:  # pragma: no cover - runs in the child process
    try:
        import resource

        # Per process: Tesseract, started from here for OCR, gets its own.
        resource.setrlimit(resource.RLIMIT_CPU, (90, 100))
        resource.setrlimit(resource.RLIMIT_AS, (_CHILD_MEMORY, _CHILD_MEMORY))
    except (ImportError, ValueError, OSError):
        pass  # macOS may refuse RLIMIT_AS; the wall-clock timeout still applies


async def parse_isolated(data: bytes, kind: str, *, seconds: float) -> list[Page]:
    """:func:`parse` in a child process with CPU, memory and time limits."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.documents.parse",
        kind,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        preexec_fn=_limit_child,
        cwd=str(Path(__file__).resolve().parents[2]),  # the backend root
    )
    try:
        out, _ = await asyncio.wait_for(process.communicate(data), timeout=seconds)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise Unsupported("The file took too long to read.") from exc
    try:
        result = json.loads(out or b"{}")
    except ValueError as exc:
        raise Unsupported("The file could not be read.") from exc
    if not result.get("ok"):
        raise Unsupported(result.get("error") or "The file could not be read.")
    return [Page(p["number"], p["text"], p.get("ocr", False)) for p in result["pages"]]


def _main() -> None:  # pragma: no cover - exercised through parse_isolated
    kind = sys.argv[1]
    data = sys.stdin.buffer.read()
    try:
        pages = parse(data, kind)
        payload = {
            "ok": True,
            "pages": [{"number": p.number, "text": p.text, "ocr": p.ocr} for p in pages],
        }
    except Unsupported as exc:
        payload = {"ok": False, "error": str(exc)}
    except Exception:  # noqa: BLE001 - never echo parser internals
        payload = {"ok": False, "error": "The file could not be read."}
    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    _main()
