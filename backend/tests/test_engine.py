"""Engine tests — every row of the decision matrix (PLAN.md §6.2) plus the
four graded edge cases. Pure functions; no LLM, no DB."""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.engine import matching, decision as de
from app.engine.confidence import composite
from app.engine.validate import arithmetic_ok
from app.schemas import (DecisionVerdict, ExtractedInvoice, ExtractionSource,
                         LineItem, MatchMethod)

D = date(2026, 9, 12)

POS = [
    {"id": 1, "po_number": "PO-2026-101", "vendor_name": "Acme Industrial Supply",
     "vendor_id": 1, "total": 12000.0, "status": "open", "issued": date(2026, 8, 20),
     "invoiced_total": 0.0,
     "lines": [{"description": "Industrial fasteners grade 8", "qty": 60, "unit_price": 85.0},
               {"description": "Safety equipment kit warehouse", "qty": 30, "unit_price": 230.0}]},
    {"id": 5, "po_number": "PO-2026-114", "vendor_name": "Northwind Logistics",
     "vendor_id": 2, "total": 9600.0, "status": "open", "issued": date(2026, 8, 28),
     "invoiced_total": 0.0,
     "lines": [{"description": "Freight services September leg", "qty": 1, "unit_price": 4800.0},
               {"description": "Freight services October leg", "qty": 1, "unit_price": 4800.0}]},
    {"id": 6, "po_number": "PO-2026-118", "vendor_name": "Globex Facilities Group",
     "vendor_id": 3, "total": 8200.0, "status": "open", "issued": date(2026, 9, 1),
     "invoiced_total": 0.0,
     "lines": [{"description": "Office lighting retrofit", "qty": 40, "unit_price": 175.0},
               {"description": "Installation labour", "qty": 8, "unit_price": 150.0}]},
    {"id": 9, "po_number": "PO-2026-127", "vendor_name": "Hooli Cloud Services",
     "vendor_id": 6, "total": 7500.0, "status": "open", "issued": date(2026, 8, 30),
     "invoiced_total": 0.0,
     "lines": [{"description": "Cloud hosting dedicated nodes", "qty": 100, "unit_price": 45.0},
               {"description": "Premium support plan", "qty": 1, "unit_price": 3000.0}]},
]


def inv(**kw) -> ExtractedInvoice:
    base = dict(vendor_name="Acme Industrial Supply", invoice_number="ACME-1",
                invoice_date=D, po_number="PO-2026-101", total=12000.0,
                subtotal=12000.0, tax=0.0,
                line_items=[LineItem(description="Industrial fasteners grade 8",
                                     qty=60, unit_price=85.0, amount=5100.0),
                            LineItem(description="Safety equipment kit warehouse",
                                     qty=30, unit_price=230.0, amount=6900.0)],
                field_confidence={"vendor_name": 0.98, "invoice_number": 0.99,
                                  "invoice_date": 0.98, "po_number": 0.99,
                                  "total": 0.99})
    base.update(kw)
    return ExtractedInvoice(**base)


def decide_with(extraction, pos=POS, **kw):
    from app.engine.validate import arithmetic_ok
    match = matching.find_po(extraction, pos)
    conf = kw.pop("confidence", None) or composite(extraction, match)
    kw.setdefault("arithmetic_ok", arithmetic_ok(extraction))
    return de.decide(extraction, match, confidence=conf, **kw), match


# ---------- happy path ----------

def test_happy_path_auto_approves_exact_match():
    d, m = decide_with(inv())
    assert m.method == MatchMethod.REF and m.delta_abs == 0
    assert d.verdict == DecisionVerdict.AUTO_APPROVE
    assert "PO_MATCHED_EXACT" in d.reason_codes
    assert d.confidence >= 0.85


def test_small_overage_within_tolerance_auto_approves_with_code():
    d, m = decide_with(inv(total=12010.0, subtotal=12000.0, tax=10.0))  # +$10 < $25 floor
    assert d.verdict == DecisionVerdict.AUTO_APPROVE
    assert "PO_MATCHED_WITHIN_TOLERANCE" in d.reason_codes


# ---------- E3: split PO ----------

def test_split_first_invoice_partial_against_balance():
    e = inv(vendor_name="Northwind Logistics", invoice_number="NW-A",
            po_number="PO-2026-114", total=4800.0, subtotal=4800.0,
            line_items=[LineItem(description="Freight services September leg",
                                 qty=1, unit_price=4800.0, amount=4800.0)])
    d, m = decide_with(e)
    assert m.po_remaining == 9600.0
    assert d.verdict == DecisionVerdict.AUTO_APPROVE
    assert "SPLIT_PO_PARTIAL" in d.reason_codes
    assert "PO_AMOUNT_EXCEEDED" not in d.reason_codes


def test_split_second_invoice_matches_remaining_balance():
    pos2 = [dict(p, invoiced_total=4800.0 if p["id"] == 5 else p["invoiced_total"])
            for p in POS]
    e = inv(vendor_name="Northwind Logistics", invoice_number="NW-B",
            po_number="PO-2026-114", total=4800.0, subtotal=4800.0,
            line_items=[LineItem(description="Freight services October leg",
                                 qty=1, unit_price=4800.0, amount=4800.0)])
    d, m = decide_with(e, pos=pos2)
    assert m.po_remaining == 4800.0 and m.delta_abs == 0
    assert d.verdict == DecisionVerdict.AUTO_APPROVE
    assert "PO_MATCHED_EXACT" in d.reason_codes


# ---------- E4: tolerance breach ----------

def test_breach_between_soft_and_hard_cap_needs_review():
    e = inv(vendor_name="Globex Facilities Group", invoice_number="GFX-1",
            po_number="PO-2026-118", total=8528.0, subtotal=8528.0)  # +4%
    d, m = decide_with(e)
    assert d.verdict == DecisionVerdict.NEEDS_REVIEW
    assert "PO_AMOUNT_EXCEEDED" in d.reason_codes
    assert d.next_action  # tells the human what to do


def test_breach_beyond_hard_cap_rejects():
    e = inv(vendor_name="Globex Facilities Group", invoice_number="GFX-2",
            po_number="PO-2026-118", total=9000.0, subtotal=9000.0)  # +9.8%
    d, _ = decide_with(e)
    assert d.verdict == DecisionVerdict.REJECT
    assert "PO_HARD_CAP_EXCEEDED" in d.reason_codes


# ---------- E2: duplicate ----------

def test_duplicate_rejects_even_when_amounts_match():
    d, _ = decide_with(inv(), duplicate=True)
    assert d.verdict == DecisionVerdict.REJECT
    assert "DUPLICATE_INVOICE_NUMBER" in d.reason_codes


def test_is_duplicate_keyed_on_vendor_and_number():
    e = inv(invoice_number="ACME-1")
    assert matching.is_duplicate(e, [("Acme Industrial Supply", "ACME-1")])
    assert not matching.is_duplicate(e, [("Acme Industrial Supply", "ACME-2")])
    assert not matching.is_duplicate(inv(invoice_number=None), [])


# ---------- E1: scanned ----------

def test_scanned_ocr_needs_review_even_on_exact_match():
    e = inv(source=ExtractionSource.OCR, field_confidence={
        "vendor_name": 0.88, "invoice_number": 0.9, "total": 0.93, "po_number": 0.91})
    d, _ = decide_with(e)
    assert d.verdict == DecisionVerdict.NEEDS_REVIEW
    assert "EXTRACTION_DEGRADED_OCR" in d.reason_codes


# ---------- B1: missing fields ----------

def test_missing_invoice_number_needs_review_with_vendor_ask():
    e = inv(invoice_number=None, po_number=None, total=12000.0)  # heuristic match
    e.field_confidence.pop("invoice_number"), e.field_confidence.pop("po_number")
    d, m = decide_with(e)
    assert m.method == MatchMethod.HEURISTIC
    assert d.verdict == DecisionVerdict.NEEDS_REVIEW
    assert "MISSING_INVOICE_NUMBER" in d.reason_codes
    assert "vendor" in d.next_action.lower()


def test_no_match_and_no_anchor_rejects():
    e = inv(vendor_name="Unknown Vendor Inc", invoice_number=None, po_number=None)
    d, _ = decide_with(e)
    assert d.verdict == DecisionVerdict.REJECT
    assert "PO_NOT_FOUND" in d.reason_codes


# ---------- B2: line-item mismatch ----------

def test_line_price_mismatch_needs_review_despite_matching_total():
    e = inv(vendor_name="Hooli Cloud Services", invoice_number="HCL-1",
            po_number="PO-2026-127", total=7500.0, subtotal=7500.0,
            line_items=[LineItem(description="Cloud hosting dedicated nodes",
                                 qty=100, unit_price=50.40, amount=5040.0),  # +12%
                        LineItem(description="Premium support plan",
                                 qty=1, unit_price=2460.0, amount=2460.0)])
    d, m = decide_with(e)
    assert m.delta_abs == 0  # totals agree…
    assert any(ld.price_deviation_pct == pytest.approx(12.0) for ld in m.line_diffs)
    assert d.verdict == DecisionVerdict.NEEDS_REVIEW  # …but unit prices don't
    assert "PO_LINE_PRICE_MISMATCH" in d.reason_codes


# ---------- guards ----------

def test_unapproved_vendor_rejects():
    d, _ = decide_with(inv(), vendor_approved=False)
    assert d.verdict == DecisionVerdict.REJECT
    assert "VENDOR_NOT_APPROVED" in d.reason_codes


def test_fully_invoiced_po_rejects():
    pos2 = [dict(p, invoiced_total=p["total"]) for p in POS]
    d, _ = decide_with(inv(), pos=pos2)
    assert d.verdict == DecisionVerdict.REJECT
    assert "PO_FULLY_INVOICED" in d.reason_codes


def test_arithmetic_mismatch_needs_review():
    e = inv(subtotal=11500.0, tax=100.0)  # lines sum to 12000, not 11500
    assert not arithmetic_ok(e)
    d, _ = decide_with(e)
    assert "ARITHMETIC_MISMATCH" in d.reason_codes
    assert d.verdict == DecisionVerdict.NEEDS_REVIEW


def test_fallback_extraction_never_auto_approves():
    e = inv(source=ExtractionSource.FALLBACK, field_confidence={
        "vendor_name": 0.75, "invoice_number": 0.75, "total": 0.75, "po_number": 0.75})
    d, _ = decide_with(e)
    assert d.verdict == DecisionVerdict.NEEDS_REVIEW
    assert "EXTRACTION_FALLBACK" in d.reason_codes


def test_heuristic_match_uses_date_window():
    e = inv(po_number=None, invoice_date=date(2026, 9, 10))
    m = matching.find_po(e, POS)
    assert m.method == MatchMethod.HEURISTIC
    old = inv(po_number=None, invoice_date=date(2025, 1, 1))
    assert matching.find_po(old, POS).method == MatchMethod.NONE


def test_arithmetic_ok_tolerates_missing_fields():
    assert arithmetic_ok(inv())
    assert arithmetic_ok(inv(subtotal=None, tax=None))
