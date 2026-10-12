"""The decision rule engine — deterministic, auditable. The LLM never decides.

Implements the decision matrix from PLAN.md §6.2 and maps every reason code
to a recommended next action so the human always knows what to do.
"""
from __future__ import annotations

from .. import config
from ..schemas import (Decision, DecisionVerdict, ExtractedInvoice,
                       MatchMethod, MatchResult)

_NEXT_ACTIONS = {
    "DUPLICATE_INVOICE_NUMBER": "Reject and notify the vendor that this invoice was already received and processed.",
    "PO_HARD_CAP_EXCEEDED": "Reject and request a credit note or a corrected PO from procurement.",
    "PO_NOT_FOUND": "Route to the AP lead to request a valid PO reference from the vendor.",
    "PO_FULLY_INVOICED": "Route to the AP lead — the PO is fully invoiced; verify with procurement before paying.",
    "VENDOR_NOT_APPROVED": "Hold payment and send the vendor through onboarding verification.",
    "ARITHMETIC_MISMATCH": "Request a corrected invoice from the vendor — the document does not add up.",
    "MISSING_INVOICE_NUMBER": "Contact the vendor to obtain the invoice number before processing.",
    "MISSING_PO_REFERENCE": "Contact the vendor for the PO reference, or confirm the heuristic match manually.",
    "MISSING_INVOICE_DATE": "Contact the vendor to obtain the invoice date (needed for terms and duplicate checks).",
    "PO_LINE_PRICE_MISMATCH": "Verify the disputed line items with the vendor before approving payment.",
    "PO_AMOUNT_EXCEEDED": "Ask procurement to confirm: request a corrected invoice or increase the PO.",
    "EXTRACTION_DEGRADED_OCR": "A human should eyeball the scanned original before approval.",
    "EXTRACTION_FALLBACK": "Re-run once the extraction service is available; verify fields manually meanwhile.",
    "MISSING_TOTAL": "The invoice total could not be read — obtain a readable copy from the vendor before processing.",
}

_REVIEW_TRIGGERS = {
    "PO_AMOUNT_EXCEEDED", "ARITHMETIC_MISMATCH", "PO_LINE_PRICE_MISMATCH",
    "MISSING_INVOICE_NUMBER", "MISSING_PO_REFERENCE", "MISSING_INVOICE_DATE",
    "EXTRACTION_DEGRADED_OCR", "EXTRACTION_FALLBACK", "MISSING_TOTAL",
}

_REJECT_CODES = {
    "DUPLICATE_INVOICE_NUMBER", "PO_HARD_CAP_EXCEEDED", "PO_FULLY_INVOICED",
    "VENDOR_NOT_APPROVED",
}

_MIN_SPLIT_RESIDUE = 1.0  # $1 left over still counts as consuming the PO whole


def _fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def _is_split(match: MatchResult) -> bool:
    """Invoice consumes only part of the PO's remaining balance."""
    left_after = (match.po_remaining or 0) - (match.invoice_total or 0.0)
    return match.within_soft_tolerance and left_after > _MIN_SPLIT_RESIDUE


def _match_codes(match: MatchResult) -> list[str]:
    if match.method == MatchMethod.NONE:
        return ["PO_NOT_FOUND"]
    primary = ("PO_FULLY_INVOICED" if match.po_fully_invoiced else
               "PO_HARD_CAP_EXCEEDED" if match.exceeds_hard_cap else
               "PO_AMOUNT_EXCEEDED" if not match.within_soft_tolerance else
               "SPLIT_PO_PARTIAL" if _is_split(match) else
               "PO_MATCHED_WITHIN_TOLERANCE" if abs(match.delta_abs or 0) >= 0.005 else
               "PO_MATCHED_EXACT")
    codes = [primary]
    if match.line_diffs:
        codes.append("PO_LINE_PRICE_MISMATCH")
    return codes


def _missing_field_codes(extraction: ExtractedInvoice, match: MatchResult) -> list[str]:
    codes = []
    if not extraction.total:  # None or 0 — no amount to match against
        codes.append("MISSING_TOTAL")
    if not extraction.invoice_number:
        codes.append("MISSING_INVOICE_NUMBER")
    if not extraction.po_number and match.method == MatchMethod.NONE:
        codes.append("MISSING_PO_REFERENCE")
    if not extraction.invoice_date:
        codes.append("MISSING_INVOICE_DATE")
    return codes


def _preamble_codes(extraction: ExtractedInvoice, match: MatchResult, *,
                    duplicate: bool, vendor_approved: bool | None,
                    arithmetic_ok: bool) -> list[str]:
    codes: list[str] = []
    if extraction.source.value == "ocr":
        codes.append("EXTRACTION_DEGRADED_OCR")
    elif extraction.source.value == "fallback":
        codes.append("EXTRACTION_FALLBACK")
    codes.extend(_missing_field_codes(extraction, match))
    if not arithmetic_ok:
        codes.append("ARITHMETIC_MISMATCH")
    if vendor_approved is False:
        codes.append("VENDOR_NOT_APPROVED")
    if duplicate:
        codes.append("DUPLICATE_INVOICE_NUMBER")
    return codes


def _match_sentence(match: MatchResult, reason_codes: list[str]) -> str:
    if not match.po_number:
        return "No purchase order could be matched to this invoice."
    how = ("explicit PO reference" if match.method == MatchMethod.REF
           else "vendor + amount + date-window heuristic")
    pct = f" ({match.delta_pct * 100:.1f}%)" if match.delta_pct is not None else ""
    sentence = (f"It matched {match.po_number} ({how}) with a remaining balance of "
                f"{_fmt_money(match.po_remaining or 0)}; the invoice differs from that "
                f"balance by {_fmt_money(match.delta_abs or 0)}{pct}.")
    if "SPLIT_PO_PARTIAL" in reason_codes:
        sentence += " This appears to be a partial invoice against a larger PO balance."
    return sentence


def _explain(extraction: ExtractedInvoice, match: MatchResult,
             reason_codes: list[str]) -> str:
    vendor = extraction.vendor_name or "Unknown vendor"
    inv_no = extraction.invoice_number or "(no invoice number)"
    src = ("scanned image via OCR" if extraction.source.value == "ocr"
           else "digital PDF text layer")
    parts = [f"Invoice {inv_no} from {vendor} for {_fmt_money(extraction.total or 0)} "
             f"was extracted from a {src}.",
             _match_sentence(match, reason_codes)]
    if reason_codes:
        parts.append("Findings: " + ", ".join(reason_codes) + ".")
    return " ".join(p for p in parts if p)


def _verdict(codes: list[str], extraction: ExtractedInvoice, match: MatchResult,
             confidence: float) -> DecisionVerdict:
    if _REJECT_CODES & set(codes):
        return DecisionVerdict.REJECT
    # an invoice with no number AND no matchable PO has nothing to anchor review to
    if "PO_NOT_FOUND" in codes and not extraction.invoice_number:
        return DecisionVerdict.REJECT
    clean = not (_REVIEW_TRIGGERS & set(codes))
    exact_enough = match.method == MatchMethod.REF and match.within_soft_tolerance
    if clean and confidence >= config.AUTO_APPROVE_CONFIDENCE and exact_enough:
        return DecisionVerdict.AUTO_APPROVE
    return DecisionVerdict.NEEDS_REVIEW


def decide(extraction: ExtractedInvoice, match: MatchResult, *,
           duplicate: bool = False,
           vendor_approved: bool | None = None,
           arithmetic_ok: bool = True,
           confidence: float | None = None) -> Decision:
    from .confidence import composite
    if confidence is None:
        confidence = composite(extraction, match)

    codes = (_preamble_codes(extraction, match, duplicate=duplicate,
                             vendor_approved=vendor_approved, arithmetic_ok=arithmetic_ok)
             + _match_codes(match))
    verdict = _verdict(codes, extraction, match, confidence)

    if verdict == DecisionVerdict.AUTO_APPROVE:
        action = "Queue for the payment batch (a human releases the batch)."
    else:
        action = next((a for c, a in _NEXT_ACTIONS.items() if c in codes), "No action needed.")

    return Decision(verdict=verdict, reason_codes=codes, confidence=confidence,
                    explanation=_explain(extraction, match, codes), next_action=action)
