"""The seven-stage pipeline: receive → classify → extract → validate →
match → decide → report. Each stage is a function that emits its own
StageEvents, so the UI can show the process thinking in real time."""
from __future__ import annotations

import hashlib
import time

from sqlalchemy.orm import Session

from ..engine import confidence as conf
from ..engine import matching
from ..engine import decision as decision_engine
from ..engine.validate import arithmetic_ok
from ..extractors import fallback as fallback_extractor
from ..extractors import llm
from ..extractors.classify import has_text_layer
from ..models import Extraction, InvoiceSeen, Match, PO, Run, StageEvent, Vendor
from ..schemas import ExtractedInvoice

STAGES = ["receive", "classify", "extract", "validate", "match", "decide", "report"]


def emit(db: Session, run: Run, stage: str, status: str, message: str = "", data: dict | None = None):
    db.add(StageEvent(run_id=run.id, stage=stage, status=status,
                      message=message, data=data or {}))
    db.commit()


def _text_of(pdf_bytes: bytes) -> str:
    try:
        from ..extractors.classify import _pages
        return "\n".join(page.extract_text() or "" for page in _pages(pdf_bytes))
    except Exception:
        return ""


def _stage_receive(db: Session, run: Run, filename: str, pdf_bytes: bytes) -> None:
    emit(db, run, "receive", "start", f"Accepted {filename}")
    run.sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    run.size = len(pdf_bytes)
    emit(db, run, "receive", "ok", f"sha256 {run.sha256[:12]}… · {run.size:,} bytes")


def _stage_classify(db: Session, run: Run, pdf_bytes: bytes) -> bool:
    emit(db, run, "classify", "start")
    digital = has_text_layer(pdf_bytes)
    kind = "DIGITAL (text layer)" if digital else "SCANNED (image — OCR required)"
    emit(db, run, "classify", "ok", f"Document type: {kind}", {"digital": digital})
    return digital


def _stage_extract(db: Session, run: Run, pdf_bytes: bytes, digital: bool):
    emit(db, run, "extract", "start",
         "Text-layer extraction via LLM" if digital else "Vision-OCR extraction via LLM")
    try:
        extraction = (llm.extract_from_text(_text_of(pdf_bytes)) if digital
                      else llm.extract_from_image(pdf_bytes))
    except Exception as exc:  # LLM down / timeout / no key — degrade, never crash
        emit(db, run, "extract", "warn",
             f"LLM extraction failed ({exc}); falling back to deterministic extractor")
        try:
            extraction = fallback_extractor.extract(pdf_bytes)
        except Exception:
            from ..schemas import ExtractionSource
            extraction = ExtractedInvoice(source=ExtractionSource.FALLBACK)
    db.add(Extraction(run_id=run.id, source=extraction.source.value,
                      fields=extraction.model_dump(mode="json"),
                      field_confidence=extraction.field_confidence))
    emit(db, run, "extract", "ok",
         f"vendor={extraction.vendor_name!r} total={extraction.total} "
         f"source={extraction.source.value}",
         extraction.model_dump(mode="json"))
    return extraction


def _stage_validate(db: Session, run: Run, extraction) -> bool:
    emit(db, run, "validate", "start")
    missing = extraction.missing_critical_fields()
    ok = arithmetic_ok(extraction)
    data = {"missing_critical_fields": missing, "arithmetic_ok": ok}
    if missing or not ok:
        emit(db, run, "validate", "warn",
             f"missing={missing or 'none'} arithmetic_ok={ok}", data)
    else:
        emit(db, run, "validate", "ok", "All critical fields present; document adds up", data)
    return ok


def _po_dicts(db: Session) -> list[dict]:
    return [{
        "id": po.id, "po_number": po.po_number, "vendor_id": po.vendor_id,
        "vendor_name": po.vendor.name if po.vendor else "",
        "total": po.total, "status": po.status, "issued": po.issued,
        "lines": [{"description": l.description, "qty": l.qty,
                   "unit_price": l.unit_price} for l in po.lines],
        "invoiced_total": po.invoiced_total,
    } for po in db.query(PO).all()]


def _stage_match(db: Session, run: Run, extraction):
    emit(db, run, "match", "start")
    seen = [(s.vendor_name, s.invoice_number) for s in db.query(InvoiceSeen).all()]
    duplicate = matching.is_duplicate(extraction, seen)
    match = matching.find_po(extraction, _po_dicts(db))
    vendor_approved = None
    if extraction.vendor_name:
        v = db.query(Vendor).filter(Vendor.name.ilike(extraction.vendor_name.strip())).first()
        vendor_approved = v.approved if v else False
    db.add(Match(run_id=run.id, po_id=match.po_id, method=match.method.value,
                 invoice_total=match.invoice_total, po_remaining=match.po_remaining,
                 delta_abs=match.delta_abs, delta_pct=match.delta_pct,
                 detail=match.model_dump(mode="json")))
    emit(db, run, "match", "ok",
         (f"matched {match.po_number} via {match.method.value}"
          if match.po_number else "no PO matched")
         + (" · DUPLICATE of prior run" if duplicate else ""),
         {**match.model_dump(mode="json"), "duplicate": duplicate})
    return match, duplicate, vendor_approved


def _stage_decide(db: Session, run: Run, extraction, match, duplicate, vendor_approved,
                  arithmetic) -> None:
    emit(db, run, "decide", "start")
    decision = decision_engine.decide(
        extraction, match, duplicate=duplicate,
        vendor_approved=vendor_approved, arithmetic_ok=arithmetic,
        confidence=conf.composite(extraction, match))
    run.decision = decision.verdict.value
    run.confidence = decision.confidence
    run.reason_codes = decision.reason_codes
    run.explanation = decision.explanation
    run.next_action = decision.next_action
    run.po_number = match.po_number
    emit(db, run, "decide", "ok",
         f"{decision.verdict.value} · confidence {decision.confidence}",
         decision.model_dump(mode="json"))


def _stage_report(db: Session, run: Run, extraction, started: float) -> None:
    emit(db, run, "report", "start")
    if extraction.invoice_number and extraction.vendor_name:
        db.add(InvoiceSeen(vendor_name=extraction.vendor_name.strip(),
                           invoice_number=extraction.invoice_number.strip(),
                           run_id=run.id))
    run.duration_ms = int((time.time() - started) * 1000)
    db.commit()
    emit(db, run, "report", "ok",
         f"Run complete in {run.duration_ms} ms · decision {run.decision}",
         {"duration_ms": run.duration_ms})


def run_pipeline(db: Session, run_id: int, filename: str, pdf_bytes: bytes) -> Run:
    started = time.time()
    run = db.get(Run, run_id)
    _stage_receive(db, run, filename, pdf_bytes)
    digital = _stage_classify(db, run, pdf_bytes)
    extraction = _stage_extract(db, run, pdf_bytes, digital)
    arithmetic = _stage_validate(db, run, extraction)
    match, duplicate, vendor_approved = _stage_match(db, run, extraction)
    _stage_decide(db, run, extraction, match, duplicate, vendor_approved, arithmetic)
    _stage_report(db, run, extraction, started)
    return run
