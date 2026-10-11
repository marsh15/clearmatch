"""End-to-end smoke: generate the invoice suite, run the real pipeline with
the LLM extraction faked deterministically (same structured output the LLM
returns), assert the decisions the demo promises. If this passes, the live
demo can't drift."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory

import pytest

from app.db import Base, SessionLocal, engine
from app.extractors import fallback as fb
from app.extractors import llm
from app.pipeline.runner import run_pipeline
from app.schemas import ExtractionSource, ExtractedInvoice, LineItem
from tools import make_invoices
from tools.seed_db import seed_reference


@pytest.fixture(scope="module", autouse=True)
def patch_llm():
    """Deterministic stand-ins for the OpenAI calls: same shapes the real
    structured outputs produce, no network."""
    def fake_text(pdf_text: str) -> ExtractedInvoice:
        e = fb.extract(text=pdf_text)
        e.source = ExtractionSource.TEXT
        e.field_confidence = {k: 0.97 for k in e.field_confidence}
        return e

    def fake_image(pdf_bytes: bytes) -> ExtractedInvoice:
        return ExtractedInvoice(
            vendor_name="Foxtrot Media Labs", invoice_number="FML-2213",
            invoice_date=date(2026, 9, 8), po_number="PO-2026-121",
            subtotal=5400.0, tax=0.0, total=5400.0,
            line_items=[LineItem(description="Q3 campaign analytics retainer",
                                 qty=3, unit_price=1800.0, amount=5400.0)],
            source=ExtractionSource.OCR,
            field_confidence={"vendor_name": 0.86, "invoice_number": 0.88,
                              "total": 0.90, "po_number": 0.87})

    saved = (llm.extract_from_text, llm.extract_from_image)
    llm.extract_from_text, llm.extract_from_image = fake_text, fake_image
    yield
    llm.extract_from_text, llm.extract_from_image = saved


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(engine)
    session = SessionLocal()
    seed_reference(session)
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="module")
def pdfs():
    tmp = tempfile.mkdtemp(prefix="clearmatch-testdata-")
    make_invoices.OUT_DIR = tmp
    make_invoices.main()
    out = {}
    for f in os.listdir(tmp):
        with open(os.path.join(tmp, f), "rb") as fh:
            out[f] = fh.read()
    return out


def _run(db, name, blob):
    from app.models import Run
    run = Run(filename=name, sha256="", size=len(blob))
    db.add(run)
    db.commit()
    return run_pipeline(db, run.id, name, blob)


def test_scanned_pdf_really_has_no_text_layer(pdfs):
    from app.extractors.classify import has_text_layer
    assert not has_text_layer(pdfs["inv_scanned_foxtrot.pdf"])
    assert has_text_layer(pdfs["inv_happy_acme.pdf"])


def test_happy_path(pdfs, db):
    run = _run(db, "inv_happy_acme.pdf", pdfs["inv_happy_acme.pdf"])
    assert run.decision == "AUTO-APPROVE"
    assert "PO_MATCHED_EXACT" in run.reason_codes
    assert run.po_number == "PO-2026-101"


def test_duplicate_after_happy(pdfs, db):
    run = _run(db, "inv_duplicate_acme.pdf", pdfs["inv_duplicate_acme.pdf"])
    assert run.decision == "REJECT"
    assert "DUPLICATE_INVOICE_NUMBER" in run.reason_codes


def test_split_a_then_b(pdfs, db):
    a = _run(db, "inv_split_a.pdf", pdfs["inv_split_a.pdf"])
    assert a.decision == "AUTO-APPROVE"
    assert "SPLIT_PO_PARTIAL" in a.reason_codes
    b = _run(db, "inv_split_b.pdf", pdfs["inv_split_b.pdf"])
    assert b.decision == "AUTO-APPROVE"
    assert "PO_MATCHED_EXACT" in b.reason_codes


def test_breach(pdfs, db):
    run = _run(db, "inv_breach_globex.pdf", pdfs["inv_breach_globex.pdf"])
    assert run.decision == "NEEDS REVIEW"
    assert "PO_AMOUNT_EXCEEDED" in run.reason_codes


def test_missing_fields(pdfs, db):
    run = _run(db, "inv_missing_initech.pdf", pdfs["inv_missing_initech.pdf"])
    assert run.decision == "NEEDS REVIEW"
    assert "MISSING_INVOICE_NUMBER" in run.reason_codes
    assert run.po_number == "PO-2026-124"  # matched heuristically


def test_line_mismatch(pdfs, db):
    run = _run(db, "inv_linemismatch_hooli.pdf", pdfs["inv_linemismatch_hooli.pdf"])
    assert run.decision == "NEEDS REVIEW"
    assert "PO_LINE_PRICE_MISMATCH" in run.reason_codes


def test_scanned_ocr_path(pdfs, db):
    run = _run(db, "inv_scanned_foxtrot.pdf", pdfs["inv_scanned_foxtrot.pdf"])
    assert run.decision == "NEEDS REVIEW"
    assert "EXTRACTION_DEGRADED_OCR" in run.reason_codes


def test_fallback_when_llm_fails(pdfs, db):
    saved = llm.extract_from_text

    def boom(*a, **k):
        raise RuntimeError("LLM down")
    llm.extract_from_text = boom
    try:
        run = _run(db, "inv_happy_acme.pdf", pdfs["inv_happy_acme.pdf"])
    finally:
        llm.extract_from_text = saved
    assert "EXTRACTION_FALLBACK" in run.reason_codes
    assert run.decision != "AUTO-APPROVE"  # never auto-approve a shaky read


def test_every_run_emits_seven_stages_in_order(pdfs, db):
    from app.models import StageEvent
    run = _run(db, "inv_happy_acme.pdf", pdfs["inv_happy_acme.pdf"])
    events = db.query(StageEvent).filter_by(run_id=run.id).order_by(StageEvent.id).all()
    seq = [e.stage for e in events]
    deduped = [s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]]
    assert deduped == ["receive", "classify", "extract", "validate",
                       "match", "decide", "report"]
    assert all(e.status in ("start", "ok", "warn") for e in events)
    assert all(any(e2.stage == s and e2.status in ("ok", "warn") for e2 in events)
               for s in deduped)  # every stage reaches a terminal state
