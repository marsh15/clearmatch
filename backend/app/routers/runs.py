"""API: create runs, stream their stages live, list/get for the dashboard.

Upload boundary guards: size cap, PDF magic bytes, filename sanitising,
per-IP rate limit (each run may call a paid LLM)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import config
from ..db import SessionLocal, get_db
from ..models import Extraction, Match, Run, StageEvent
from ..pipeline.runner import run_pipeline

router = APIRouter(prefix="/api")

PRESET_DIR = os.environ.get("PRESET_DIR", os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "testdata"))

ALLOWED_PRESETS = {
    "happy": "inv_happy_acme.pdf",
    "scanned": "inv_scanned_foxtrot.pdf",
    "duplicate": "inv_duplicate_acme.pdf",
    "split_a": "inv_split_a.pdf",
    "split_b": "inv_split_b.pdf",
    "breach": "inv_breach_globex.pdf",
    "missing": "inv_missing_initech.pdf",
    "linemismatch": "inv_linemismatch_hooli.pdf",
}

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._\- ]")


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(name or "invoice.pdf")[:200]
    return _SAFE_FILENAME.sub("_", name) or "invoice.pdf"


# ponytail: per-process limiter; Redis-backed if this ever runs on >1 dyno
_hits: dict[str, list[float]] = {}


def _rate_limited(ip: str) -> bool:
    now = time.time()
    window = [t for t in _hits.get(ip, []) if now - t < 3600]
    _hits[ip] = window
    if len(window) >= config.RUN_RATE_LIMIT_PER_HOUR:
        return True
    window.append(now)
    return False


def _check_run_allowed(request: Request, pdf_bytes: bytes) -> str:
    if _rate_limited(request.client.host if request.client else "unknown"):
        raise HTTPException(429, "Too many runs from this address — try again later")
    if len(pdf_bytes) > config.MAX_PDF_BYTES:
        raise HTTPException(413, f"PDF too large (max {config.MAX_PDF_BYTES // (1024*1024)} MB)")
    if not pdf_bytes.lstrip()[:5].startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF invoice files are accepted")
    return ""


def _start_run(db: Session, filename: str, pdf_bytes: bytes) -> Run:
    run = Run(filename=filename, sha256="", size=len(pdf_bytes))
    db.add(run)
    db.commit()
    return run


async def _execute(run_id: int, filename: str, pdf_bytes: bytes):
    db = SessionLocal()
    try:
        run_pipeline(db, run_id, filename, pdf_bytes)
    finally:
        db.close()


@router.post("/runs")
async def create_run(request: Request, background: BackgroundTasks,
                     file: UploadFile = File(...), db: Session = Depends(get_db)):
    pdf_bytes = await file.read(config.MAX_PDF_BYTES + 1)
    if not pdf_bytes:
        raise HTTPException(400, "Empty upload")
    _check_run_allowed(request, pdf_bytes)
    filename = _sanitize_filename(file.filename)
    run = _start_run(db, filename, pdf_bytes)
    background.add_task(_execute, run.id, filename, pdf_bytes)
    return {"run_id": run.id}


@router.post("/runs/preset/{preset}")
async def create_preset_run(preset: str, request: Request, background: BackgroundTasks,
                            db: Session = Depends(get_db)):
    if preset not in ALLOWED_PRESETS:
        raise HTTPException(404, f"Unknown preset {preset}")
    path = os.path.join(PRESET_DIR, ALLOWED_PRESETS[preset])
    if not os.path.exists(path):
        raise HTTPException(500, f"Preset file missing: {path}")
    with open(path, "rb") as f:
        pdf_bytes = f.read()
    _check_run_allowed(request, pdf_bytes)
    run = _start_run(db, ALLOWED_PRESETS[preset], pdf_bytes)
    background.add_task(_execute, run.id, ALLOWED_PRESETS[preset], pdf_bytes)
    return {"run_id": run.id}


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.id.desc()).limit(100).all()
    return [{
        "id": r.id, "filename": r.filename, "decision": r.decision,
        "confidence": r.confidence, "reason_codes": r.reason_codes,
        "po_number": r.po_number, "duration_ms": r.duration_ms,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    extraction = db.query(Extraction).filter_by(run_id=run.id).first()
    match = db.query(Match).filter_by(run_id=run.id).first()
    events = db.query(StageEvent).filter_by(run_id=run.id).order_by(StageEvent.id).all()
    return {
        "id": run.id, "filename": run.filename, "sha256": run.sha256,
        "size": run.size, "decision": run.decision, "confidence": run.confidence,
        "reason_codes": run.reason_codes, "explanation": run.explanation,
        "next_action": run.next_action, "po_number": run.po_number,
        "duration_ms": run.duration_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "extraction": extraction.fields if extraction else None,
        "extraction_source": extraction.source if extraction else None,
        "match": match.detail if match else None,
        "events": [{"id": e.id, "stage": e.stage, "status": e.status,
                    "message": e.message, "data": e.data,
                    "ts": e.ts.isoformat() if e.ts else None} for e in events],
    }


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: int, db: Session = Depends(get_db)):
    """SSE: emits each stage event as it lands; closes after the report stage
    or SSE_MAX_SECONDS, whichever comes first."""
    if not db.get(Run, run_id):
        raise HTTPException(404, "Run not found")
    db.close()

    async def gen():
        seen = 0
        done = False
        deadline = time.time() + config.SSE_MAX_SECONDS
        session = SessionLocal()
        try:
            while not done and time.time() < deadline:
                events = session.query(StageEvent).filter(
                    StageEvent.run_id == run_id, StageEvent.id > seen
                ).order_by(StageEvent.id).all()
                for e in events:
                    seen = e.id
                    payload = json.dumps({
                        "id": e.id, "stage": e.stage, "status": e.status,
                        "message": e.message, "data": e.data,
                        "ts": e.ts.isoformat() if e.ts else None})
                    yield f"event: stage\ndata: {payload}\n\n"
                    if e.stage == "report" and e.status == "ok":
                        done = True
                session.expire_all()
                await asyncio.sleep(0.3)
        finally:
            session.close()

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/presets")
def presets():
    return [{"key": k, "filename": v} for k, v in ALLOWED_PRESETS.items()]
