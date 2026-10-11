"""Pydantic schemas — the contracts passed between pipeline stages."""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExtractionSource(str, Enum):
    TEXT = "text"            # digital PDF, LLM over text layer
    OCR = "ocr"              # scanned image, vision model
    FALLBACK = "fallback"    # LLM unavailable, deterministic regex extractor


class LineItem(BaseModel):
    description: str = ""
    qty: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


class ExtractedInvoice(BaseModel):
    vendor_name: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    po_number: Optional[str] = None
    currency: str = "USD"
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    source: ExtractionSource = ExtractionSource.TEXT
    # per-field extraction confidence (0..1)
    field_confidence: dict[str, float] = Field(default_factory=dict)

    def missing_critical_fields(self) -> list[str]:
        missing = []
        if not self.invoice_number:
            missing.append("invoice_number")
        if not self.invoice_date:
            missing.append("invoice_date")
        return missing


class MatchMethod(str, Enum):
    REF = "ref"              # explicit PO number on the invoice
    HEURISTIC = "heuristic"  # vendor + amount + date window
    NONE = "none"


class LineDiff(BaseModel):
    description: str = ""
    po_qty: Optional[float] = None
    po_unit_price: Optional[float] = None
    invoice_qty: Optional[float] = None
    invoice_unit_price: Optional[float] = None
    price_deviation_pct: Optional[float] = None


class MatchResult(BaseModel):
    po_id: Optional[int] = None
    po_number: Optional[str] = None
    method: MatchMethod = MatchMethod.NONE
    invoice_total: Optional[float] = None
    po_remaining: Optional[float] = None
    delta_abs: Optional[float] = None      # invoice - remaining
    delta_pct: Optional[float] = None      # delta_abs / remaining
    within_soft_tolerance: bool = False
    exceeds_hard_cap: bool = False
    po_fully_invoiced: bool = False
    line_diffs: list[LineDiff] = Field(default_factory=list)
    matched_lines: int = 0


class DecisionVerdict(str, Enum):
    AUTO_APPROVE = "AUTO-APPROVE"
    NEEDS_REVIEW = "NEEDS REVIEW"
    REJECT = "REJECT"


class Decision(BaseModel):
    verdict: DecisionVerdict
    reason_codes: list[str]
    confidence: float
    explanation: str
    next_action: str
