"""Reference data + demo hygiene endpoints."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PO, Run, Vendor

router = APIRouter(prefix="/api")


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.query(Vendor).limit(1).all()
    return {"status": "ok"}


@router.get("/vendors")
def vendors(db: Session = Depends(get_db)):
    return [{"id": v.id, "name": v.name, "tax_id": v.tax_id, "approved": v.approved}
            for v in db.query(Vendor).all()]


@router.get("/pos")
def pos(db: Session = Depends(get_db)):
    out = []
    for po in db.query(PO).all():
        out.append({
            "id": po.id, "po_number": po.po_number,
            "vendor": po.vendor.name if po.vendor else None,
            "total": po.total, "invoiced_total": po.invoiced_total,
            "remaining": round(po.total - po.invoiced_total, 2),
            "status": po.status, "issued": po.issued.isoformat(),
            "lines": [{"description": l.description, "qty": l.qty,
                       "unit_price": l.unit_price} for l in po.lines],
        })
    return out


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    runs = db.query(Run).all()
    mix: dict[str, int] = {}
    for r in runs:
        mix[r.decision] = mix.get(r.decision, 0) + 1
    return {"total_runs": len(runs), "decision_mix": mix,
            "avg_duration_ms": round(sum(r.duration_ms for r in runs) / len(runs)) if runs else 0}


@router.post("/seed/reset")
def seed_reset(request: Request, db: Session = Depends(get_db)):
    """Restore pristine demo state: wipe runs, re-seed reference data.
    Destructive — if RESET_TOKEN is set in the env, callers must send it
    in the X-Reset-Token header."""
    token = os.environ.get("RESET_TOKEN")
    if token and request.headers.get("X-Reset-Token") != token:
        raise HTTPException(401, "Reset token required")
    from tools.seed_db import reseed
    reseed(db)
    return {"status": "reset"}
