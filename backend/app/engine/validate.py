"""Document self-consistency checks — does the invoice add up?"""
from __future__ import annotations

from ..schemas import ExtractedInvoice


def _line_math_ok(inv: ExtractedInvoice, tol: float) -> bool:
    return all(None in (li.qty, li.unit_price, li.amount)
               or abs(li.qty * li.unit_price - li.amount) <= tol
               for li in inv.line_items)


def _lines_sum_to_subtotal(inv: ExtractedInvoice, tol: float) -> bool:
    if not inv.line_items or inv.subtotal is None:
        return True
    line_sum = sum(li.amount for li in inv.line_items if li.amount is not None)
    return abs(line_sum - inv.subtotal) <= tol


def _totals_reconcile(inv: ExtractedInvoice, tol: float) -> bool:
    if inv.subtotal is None or inv.total is None:
        return True
    expected = inv.subtotal + (inv.tax or 0.0) if inv.tax is not None else inv.subtotal
    return abs(expected - inv.total) <= tol


def arithmetic_ok(inv: ExtractedInvoice, *, cent_tolerance: float = 0.05) -> bool:
    """Σ line amounts ≈ subtotal, subtotal + tax ≈ total, qty × unit ≈ amount.
    Absent fields don't fail the check — MISSING_* codes handle those; this
    only flags numbers that contradict each other."""
    tol = cent_tolerance
    return (_line_math_ok(inv, tol)
            and _lines_sum_to_subtotal(inv, tol)
            and _totals_reconcile(inv, tol))
