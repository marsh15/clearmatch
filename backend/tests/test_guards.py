"""Boundary-guard tests: upload validation, rate limiting, hostile LLM output,
and the missing-total engine hole. These are the abuse cases from the
threat model — each is the misuse test for a use case."""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# file-backed, not :memory: — TestClient runs lifespan and requests on
# different connections, and in-memory DBs don't share across them
os.environ["DATABASE_URL"] = "sqlite:///./.clearmatch-test.db"
if os.path.exists(".clearmatch-test.db"):
    os.remove(".clearmatch-test.db")

import pytest
from fastapi.testclient import TestClient

from app import config
from app.extractors import llm
from app.schemas import DecisionVerdict, ExtractionSource

FAKE_PDF = b"%PDF-1.4 fake-invoice-bytes"


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:  # runs startup: create_all + seed
        yield c


def test_rejects_non_pdf_magic_bytes(client):
    r = client.post("/api/runs", files={"file": ("evil.txt", b"just text", "application/pdf")})
    assert r.status_code == 400


def test_rejects_oversized_upload(client):
    big = b"%PDF-1.4" + b"0" * (config.MAX_PDF_BYTES + 1)
    r = client.post("/api/runs", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413


def test_rejects_empty_upload(client):
    r = client.post("/api/runs", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert r.status_code == 400


def test_filename_is_sanitised(client):
    r = client.post("/api/runs",
                    files={"file": ("../../etc/passwd.pdf", FAKE_PDF, "application/pdf")})
    assert r.status_code == 200
    run = client.get(f"/api/runs/{r.json()['run_id']}").json()
    assert run["filename"] == "passwd.pdf"


def test_rate_limit_kicks_in(client, monkeypatch):
    monkeypatch.setattr(config, "RUN_RATE_LIMIT_PER_HOUR", 1)
    from app.routers import runs as runs_router
    runs_router._hits.clear()
    r1 = client.post("/api/runs", files={"file": ("a.pdf", FAKE_PDF, "application/pdf")})
    r2 = client.post("/api/runs", files={"file": ("b.pdf", FAKE_PDF, "application/pdf")})
    assert r1.status_code == 200
    assert r2.status_code == 429


def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_reset_token_gate(monkeypatch, client):
    monkeypatch.setenv("RESET_TOKEN", "s3cret")
    r = client.post("/api/seed/reset")
    assert r.status_code == 401
    r = client.post("/api/seed/reset", headers={"X-Reset-Token": "s3cret"})
    assert r.status_code == 200


# --- hostile LLM output (OWASP LLM05: model output is untrusted input) ---

def test_llm_output_negative_and_nan_numbers_nulled():
    inv = llm._to_invoice({
        "vendor_name": "V" * 500, "invoice_number": "X-1",
        "total": -5000.0, "subtotal": float("nan"), "tax": float("inf"),
        "po_number": "PO-1", "currency": "USD",
        "line_items": [{"description": "D", "qty": 2, "unit_price": 10.0, "amount": 20.0}],
        "field_confidence": {"total": 0.99},
    }, ExtractionSource.TEXT)
    assert inv.total is None            # negative money is garbage, not data
    assert inv.subtotal is None         # NaN
    assert inv.tax is None              # inf
    assert len(inv.vendor_name) == 200  # length-capped


def test_llm_output_garbage_tolerated():
    inv = llm._to_invoice({"line_items": "not-a-list", "total": "12.5"},
                          ExtractionSource.TEXT)
    assert inv.line_items == []
    assert inv.total == 12.5


# --- the $0-invoice engine hole ---

def test_missing_total_never_auto_approves():
    from app.engine import matching
    from app.engine.decision import decide
    from tests.test_engine import POS, inv
    e = inv(total=None, subtotal=None)
    match = matching.find_po(e, POS)
    d = decide(e, match, arithmetic_ok=False)
    assert "MISSING_TOTAL" in d.reason_codes
    assert d.verdict != DecisionVerdict.AUTO_APPROVE


def test_zero_total_never_auto_approves():
    from app.engine import matching
    from app.engine.decision import decide
    from tests.test_engine import POS, inv
    e = inv(total=0.0, subtotal=0.0)
    match = matching.find_po(e, POS)
    d = decide(e, match, arithmetic_ok=False)
    assert "MISSING_TOTAL" in d.reason_codes
    assert d.verdict != DecisionVerdict.AUTO_APPROVE
