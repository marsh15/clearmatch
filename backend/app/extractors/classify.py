"""Stage 2 — classify the PDF: digital text layer or scanned image?"""
from __future__ import annotations

import io

from pypdf import PdfReader

from .. import config

MIN_TEXT_CHARS = 40  # a real invoice's text layer has far more than this


def _pages(pdf_bytes: bytes) -> list:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return reader.pages[:config.MAX_PDF_PAGES]  # page-bomb guard


def has_text_layer(pdf_bytes: bytes) -> bool:
    try:
        text = "".join(page.extract_text() or "" for page in _pages(pdf_bytes))
        return len(text.strip()) >= MIN_TEXT_CHARS
    except Exception:
        return False
