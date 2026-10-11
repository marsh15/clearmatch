"""Deterministic fallback extractor — runs when the LLM is unavailable.

Handles our generated invoice format (and most simple text-layer invoices)
with plain regex. Confidence is capped by config.CONF_FALLBACK downstream, so
a fallback extraction can never drive an AUTO-APPROVE.
"""
from __future__ import annotations

import io
import re
from datetime import date

from pypdf import PdfReader

from ..schemas import ExtractedInvoice, ExtractionSource, LineItem

_MONEY = r"\$?\s*([\d,]+(?:\.\d{2})?)"

_NULL_WORDS = {"-", "\u2014", "n/a", "na", "none", "not provided", ""}


def _clean(value: str | None) -> str | None:
    v = (value or "").strip()
    return None if v.lower() in _NULL_WORDS else v


def _money(s: str) -> float | None:
    m = re.search(_MONEY, s)
    return float(m.group(1).replace(",", "")) if m else None


# --- one tiny rule per header field: line-anchored regex + value extractor ---

def _r_invoice_number(m) -> tuple[str, str] | None:
    v = _clean(m.group(1))
    return ("invoice_number", v.upper()) if v else None


def _r_po_number(m) -> tuple[str, str] | None:
    v = _clean(m.group(1))
    # a bare number is a price fragment, not a PO reference
    return ("po_number", v.upper()) if v and not v.isdigit() else None


def _r_date(m) -> tuple[str, date]:
    y, mo, d = map(int, m.group(1).split("-"))
    return ("invoice_date", date(y, mo, d))


def _r_vendor(m) -> tuple[str, str] | None:
    v = _clean(m.group(1))
    return ("vendor_name", v.title()) if v else None


def _r_subtotal(m) -> tuple[str, float] | None:
    v = _money(m.group(1))
    return ("subtotal", v) if v is not None else None


def _r_tax(m) -> tuple[str, float] | None:
    v = _money(m.group(1))
    return ("tax", v) if v is not None else None


def _r_total(m) -> tuple[str, float] | None:
    v = _money(m.group(1))
    return ("total", v) if v is not None else None


_RULES: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*(.+)$", re.I), _r_invoice_number),
    (re.compile(r"(?:p\.?o\.?|purchase\s*order)\s*(?:number|no\.?|#|ref)?\s*[:\-]?\s*([A-Z0-9\-]+)", re.I), _r_po_number),
    (re.compile(r"(?:invoice\s*)?date\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", re.I), _r_date),
    (re.compile(r"vendor\s*[:\-]?\s*(.+)$", re.I), _r_vendor),
    (re.compile(r"subtotal\s*[:\-]?\s*(.*)$", re.I), _r_subtotal),
    (re.compile(r"(?:sales\s*tax|tax|vat)\s*[:\-]?\s*(.*)$", re.I), _r_tax),
    # longest labels first so alternation picks the specific one
    (re.compile(r"(?:invoice\s*total|balance\s*due|amount\s*due|total\s*due|total)\s*[:\-]?\s*(.*)$", re.I), _r_total),
]

# "<description>  60 x $85.00  $5,100.00" or "<description>  60 $85.00  $5,100.00"
_LINE_RE = re.compile(
    r"^(.+?)\s+(\d+(?:\.\d+)?)\s*(?:[x×]\s*)?\$([\d,]+\.?\d*)\s+\$?([\d,]+\.?\d*)$")


def _line_item(m) -> LineItem:
    desc, qty, unit, amt = m.groups()
    return LineItem(description=desc.strip(), qty=float(qty),
                    unit_price=float(unit.replace(",", "")),
                    amount=float(amt.replace(",", "")))


def _apply_header_rule(inv: ExtractedInvoice, line: str) -> None:
    for pattern, rule in _RULES:
        m = pattern.match(line)
        if m and (hit := rule(m)) and getattr(inv, hit[0]) is None:
            setattr(inv, *hit)


def extract(pdf_bytes: bytes | None = None, *, text: str | None = None) -> ExtractedInvoice:
    if text is None:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    inv = ExtractedInvoice(source=ExtractionSource.FALLBACK)
    for ln in lines:
        li = _LINE_RE.match(ln)
        if li:
            inv.line_items.append(_line_item(li))
        else:
            _apply_header_rule(inv, ln)

    inv.field_confidence = {
        f: 0.75 for f in ("vendor_name", "invoice_number", "invoice_date",
                          "po_number", "subtotal", "tax", "total")
        if getattr(inv, f) is not None}
    return inv
