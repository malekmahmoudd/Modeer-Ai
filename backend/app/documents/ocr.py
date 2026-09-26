"""Reading text from photos and scanned PDF pages (OCR), locally.

Tesseract does the reading, with its Arabic and English "best" models (fetched
and verified by fetch_ocr.py). Nothing leaves the server. Before reading, each
image is cleaned up with Pillow: turned the right way up from its EXIF
orientation, made greyscale, scaled so text is a readable size, and given its
full contrast range. Metadata (including GPS) is dropped with the original.

OCR is slower and less exact than a real text layer, so a document read this
way says so, and only the first pages of a long scan are read.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
from pathlib import Path

#: Pages of a scanned PDF read at most; the rest are skipped with a note.
MAX_OCR_PAGES = 15
#: Longest side, in pixels, an image is scaled to before reading. Tesseract reads
#: best with capital letters ~30px tall; a phone photo of a page at 2000–3000px
#: is about right, and much larger only costs time.
_TARGET_SIDE = 2400
_MAX_PIXELS = 40_000_000
_PAGE_SECONDS = 40
#: Rendering scale for scanned PDF pages: 72 dpi x 4 ≈ 300 dpi.
_PDF_SCALE = 300 / 72
_BIDI_MARKS = dict.fromkeys(map(ord, "\u200e\u200f\u202a\u202b\u202c\u202d\u202e"))


def tessdata_dir() -> Path:
    configured = os.environ.get("OCR_TESSDATA_DIR", "models/tessdata")
    path = Path(configured)
    return path if path.is_absolute() else Path(__file__).resolve().parents[2] / path


def available() -> bool:
    """Tesseract is installed and both language files are present."""
    data = tessdata_dir()
    return (
        shutil.which("tesseract") is not None
        and (data / "ara.traineddata").is_file()
        and (data / "eng.traineddata").is_file()
    )


def prepare(image):
    """A cleaned-up greyscale copy of ``image`` for reading."""
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        # Transparent areas read as black; put the picture on white first.
        rgba = image.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        image = Image.alpha_composite(white, rgba)
    image = image.convert("L")
    longest = max(image.size)
    if longest and longest != _TARGET_SIDE and (longest < 1600 or longest > 3600):
        factor = _TARGET_SIDE / longest
        image = image.resize(
            (max(1, round(image.width * factor)), max(1, round(image.height * factor))),
            Image.LANCZOS,
        )
    return ImageOps.autocontrast(image, cutoff=1)


def read_image(image) -> str:
    """The text in one prepared image, Arabic and English."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    result = subprocess.run(
        [
            "tesseract",
            "stdin",
            "stdout",
            "--tessdata-dir",
            str(tessdata_dir()),
            "-l",
            "ara+eng",
            "--psm",
            "3",
        ],
        input=buffer.getvalue(),
        capture_output=True,
        timeout=_PAGE_SECONDS,
        env={**os.environ, "OMP_THREAD_LIMIT": "2"},
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("tesseract failed")
    # Tesseract wraps mixed-direction runs in invisible LRM/RLM marks, which
    # would stop a search for the word from matching.
    return result.stdout.decode("utf-8", errors="replace").translate(_BIDI_MARKS)


def open_image(data: bytes):
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = _MAX_PIXELS  # decompression-bomb guard
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def pdf_pages(data: bytes, numbers: list[int]):
    """Rendered images of the given 1-based PDF pages."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(data)
    try:
        for number in numbers:
            page = document[number - 1]
            try:
                yield number, page.render(scale=_PDF_SCALE, grayscale=True).to_pil()
            finally:
                page.close()
    finally:
        document.close()
