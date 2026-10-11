"""PO matching — pure functions, no DB, no LLM.

A PO dict looks like:
    {"id": 1, "po_number": "PO-2026-101", "vendor_name": "Acme Corp",
     "vendor_id": 1, "total": 12000.0, "status": "open", "issued": date(...),
     "lines": [{"description": "...", "qty": 10, "unit_price": 100.0}],
     "invoiced_total": 0.0}
"""
from __future__ import annotations

from datetime import date

from .. import config
from ..schemas import ExtractedInvoice, LineDiff, MatchMethod, MatchResult


def soft_tolerance(po_remaining: float) -> float:
    return max(config.SOFT_TOLERANCE_ABS, abs(po_remaining) * config.SOFT_TOLERANCE_PCT)


def po_remaining(po: dict) -> float:
    return round(po["total"] - po.get("invoiced_total", 0.0), 2)


def is_duplicate(extraction: ExtractedInvoice, seen: list[tuple[str, str]]) -> bool:
    if not extraction.invoice_number or not extraction.vendor_name:
        return False
    key = (extraction.vendor_name.strip().lower(), extraction.invoice_number.strip().lower())
    return key in [(v.lower(), n.lower()) for v, n in seen]


def _tokenize(s: str) -> set[str]:
    return set("".join(c.lower() if c.isalnum() else " " for c in s).split())


def _best_po_line(description: str, po_lines: list[dict]) -> dict | None:
    """PO line whose description overlaps the invoice line's the most."""
    inv_tokens = _tokenize(description)
    best, best_score = None, 0.0
    for po_line in po_lines:
        po_tokens = _tokenize(po_line["description"])
        if not inv_tokens or not po_tokens:
            continue
        score = len(inv_tokens & po_tokens) / len(inv_tokens | po_tokens)
        if score > best_score:
            best, best_score = po_line, score
    return best if best_score >= 0.3 else None


def _line_diffs(extraction: ExtractedInvoice, po: dict) -> tuple[list[LineDiff], int]:
    """Flag invoice lines whose unit price deviates beyond
    LINE_PRICE_MISMATCH_PCT from the matched PO line."""
    diffs: list[LineDiff] = []
    matched = 0
    for inv_line in extraction.line_items:
        po_line = _best_po_line(inv_line.description, po.get("lines", []))
        if po_line is None or inv_line.unit_price is None:
            continue
        matched += 1
        po_price = float(po_line["unit_price"])
        if po_price:
            dev = (inv_line.unit_price - po_price) / po_price
            if abs(dev) > config.LINE_PRICE_MISMATCH_PCT:
                diffs.append(LineDiff(
                    description=po_line["description"],
                    po_qty=po_line.get("qty"), po_unit_price=po_price,
                    invoice_qty=inv_line.qty, invoice_unit_price=inv_line.unit_price,
                    price_deviation_pct=round(dev * 100, 1)))
    return diffs, matched


def _find_by_ref(extraction: ExtractedInvoice, pos: list[dict]) -> dict | None:
    if not extraction.po_number:
        return None
    ref = extraction.po_number.strip().lower()
    return next((p for p in pos if p["po_number"].strip().lower() == ref), None)


def _date_window_ok(po_issued: date, invoice_date: date | None) -> bool:
    if invoice_date is None:
        return True  # can't judge the window; the field-level check will flag it
    delta = (invoice_date - po_issued).days
    return -14 <= delta <= config.HEURISTIC_MATCH_WINDOW_DAYS


def _find_by_heuristic(extraction: ExtractedInvoice, pos: list[dict]) -> dict | None:
    """Vendor + amount-within-tolerance + PO-issued-in-date-window."""
    if not extraction.vendor_name or extraction.total is None:
        return None
    vendor = extraction.vendor_name.strip().lower()
    for candidate in pos:
        if candidate.get("vendor_name", "").strip().lower() != vendor:
            continue
        remaining = po_remaining(candidate)
        if abs(extraction.total - remaining) <= soft_tolerance(remaining) \
                and _date_window_ok(candidate["issued"], extraction.invoice_date):
            return candidate
    return None


def _assess(extraction: ExtractedInvoice, po: dict, method: MatchMethod) -> MatchResult:
    """Compare the invoice against the matched PO's remaining balance."""
    remaining = po_remaining(po)
    delta_abs = round((extraction.total or 0.0) - remaining, 2)
    delta_pct = round(delta_abs / remaining, 4) if remaining else None
    diffs, matched = _line_diffs(extraction, po)
    return MatchResult(
        po_id=po["id"], po_number=po["po_number"], method=method,
        invoice_total=extraction.total, po_remaining=remaining,
        delta_abs=delta_abs, delta_pct=delta_pct,
        # One-sided tolerance: over-billing beyond the allowance is a breach;
        # under-billing (partial draw / split PO) is legitimate.
        within_soft_tolerance=delta_abs <= soft_tolerance(remaining),
        exceeds_hard_cap=delta_pct is not None and delta_pct > config.HARD_CAP_PCT,
        po_fully_invoiced=remaining <= 0.005,
        line_diffs=diffs, matched_lines=matched)


def find_po(extraction: ExtractedInvoice, pos: list[dict]) -> MatchResult:
    """Match an invoice to a PO: explicit reference first, then
    vendor + amount + date-window heuristic. Always remaining-balance aware."""
    result = MatchResult(invoice_total=extraction.total)
    po = _find_by_ref(extraction, pos)
    method = MatchMethod.REF
    if po is None:
        po = _find_by_heuristic(extraction, pos)
        method = MatchMethod.HEURISTIC
    if po is None:
        return result
    return _assess(extraction, po, method)
