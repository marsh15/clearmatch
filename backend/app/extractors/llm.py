"""LLM extraction with OpenAI structured outputs — the perception layer.

The LLM reads the invoice (text layer or image) and returns strict JSON plus
per-field confidence. It never makes the payment decision (see engine/decision.py).
"""
from __future__ import annotations

import io
import json
import math
import os
import re
from datetime import date

from .. import config
from ..schemas import ExtractedInvoice, ExtractionSource, LineItem

SYSTEM_PROMPT = """You extract structured data from vendor invoice PDFs for an
accounts-payable pipeline. Return ONLY the fields you can actually see in the
document; use null for anything absent — never guess. Report a per-field
confidence between 0 and 1 in field_confidence for every non-null field."""

SCHEMA = {
    "type": "object",
    "properties": {
        "vendor_name": {"type": ["string", "null"]},
        "vendor_tax_id": {"type": ["string", "null"]},
        "invoice_number": {"type": ["string", "null"]},
        "invoice_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
        "po_number": {"type": ["string", "null"]},
        "currency": {"type": "string"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "qty": {"type": ["number", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "amount": {"type": ["number", "null"]},
                },
            },
        },
        "subtotal": {"type": ["number", "null"]},
        "tax": {"type": ["number", "null"]},
        "total": {"type": ["number", "null"]},
        "field_confidence": {"type": "object"},
    },
    "required": ["vendor_name", "invoice_number", "total", "line_items"],
}


def _client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key, timeout=config.OPENAI_TIMEOUT_S)


def _parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(value))
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _num(v) -> float | None:
    """Model output is untrusted (OWASP LLM05): reject non-finite/negative numbers."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f >= 0 else None


def _txt(v, limit: int = 200) -> str | None:
    if not isinstance(v, str):
        return None
    v = v.strip()
    return v[:limit] or None


def _conf(v) -> float | None:
    """Confidence values are untrusted too: keep them finite and in [0, 1]."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    f = float(v)
    return min(1.0, max(0.0, f)) if math.isfinite(f) else None


def _to_invoice(data: dict, source: ExtractionSource) -> ExtractedInvoice:
    line_items = [LineItem(description=_txt(li.get("description"), 300) or "",
                           qty=_num(li.get("qty")),
                           unit_price=_num(li.get("unit_price")),
                           amount=_num(li.get("amount")))
                  for li in data.get("line_items", [])
                  if isinstance(li, dict)]
    return ExtractedInvoice(
        vendor_name=_txt(data.get("vendor_name")),
        vendor_tax_id=_txt(data.get("vendor_tax_id"), 50),
        invoice_number=_txt(data.get("invoice_number"), 100),
        invoice_date=_parse_date(data.get("invoice_date")),
        po_number=_txt(data.get("po_number"), 50),
        currency=(_txt(data.get("currency"), 8) or config.CURRENCY),
        line_items=line_items,
        subtotal=_num(data.get("subtotal")),
        tax=_num(data.get("tax")),
        total=_num(data.get("total")),
        source=source,
        field_confidence={k: c for k, v in (data.get("field_confidence") or {}).items()
                          if (c := _conf(v)) is not None},
    )


def extract_from_text(pdf_text: str) -> ExtractedInvoice:
    """Digital PDF: send the text layer through the chat API with structured output."""
    client = _client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY not set")
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract this invoice text:\n\n{pdf_text[:15000]}"},
        ],
        response_format={"type": "json_schema", "json_schema": {
            "name": "invoice", "strict": False, "schema": SCHEMA}},
    )
    data = json.loads(resp.choices[0].message.content)
    return _to_invoice(data, ExtractionSource.TEXT)


def extract_from_image(pdf_bytes: bytes) -> ExtractedInvoice:
    """Scanned PDF: send the raw PDF pages to the vision model."""
    client = _client()
    if client is None:
        raise RuntimeError("OPENAI_API_KEY not set")
    import base64
    b64 = base64.b64encode(pdf_bytes).decode()
    resp = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Extract this scanned invoice."},
                {"type": "image_url", "image_url": {"url": f"data:application/pdf;base64,{b64}"}},
            ]},
        ],
        response_format={"type": "json_schema", "json_schema": {
            "name": "invoice", "strict": False, "schema": SCHEMA}},
    )
    data = json.loads(resp.choices[0].message.content)
    return _to_invoice(data, ExtractionSource.OCR)
