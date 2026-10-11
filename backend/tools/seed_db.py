"""Reference data: vendors + POs engineered so every demo scenario has a
deterministic landing spot (PLAN.md §8.1). Dates are relative to the case
study week (Sep 2026)."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import PO, POLine, InvoiceSeen, Match, Run, StageEvent, Extraction, Vendor

VENDORS = [
    {"name": "Acme Industrial Supply", "tax_id": "US-EIN 47-2231845", "approved": True},
    {"name": "Northwind Logistics", "tax_id": "US-EIN 84-1109372", "approved": True},
    {"name": "Globex Facilities Group", "tax_id": "US-EIN 59-3847261", "approved": True},
    {"name": "Foxtrot Media Labs", "tax_id": "US-EIN 77-0918273", "approved": True},
    {"name": "Initech Systems", "tax_id": "US-EIN 31-4472905", "approved": True},
    {"name": "Hooli Cloud Services", "tax_id": "US-EIN 82-6610478", "approved": True},
    {"name": "Umbrella Facilities Corp", "tax_id": "US-EIN 63-8801129", "approved": False},
]

POS = [
    {"po_number": "PO-2026-101", "vendor": "Acme Industrial Supply", "total": 12000.00,
     "issued": date(2026, 8, 20), "lines": [
         ("Industrial fasteners, grade 8 (box of 500)", 60, 85.00),
         ("Safety equipment kit — warehouse", 30, 230.00)]},
    {"po_number": "PO-2026-104", "vendor": "Acme Industrial Supply", "total": 3150.00,
     "issued": date(2026, 9, 2), "lines": [
         ("Replacement conveyor belts", 9, 350.00)]},
    {"po_number": "PO-2026-107", "vendor": "Northwind Logistics", "total": 2400.00,
     "issued": date(2026, 7, 15), "status": "closed", "lines": [
         ("Pallet storage — July", 1, 2400.00)]},
    {"po_number": "PO-2026-110", "vendor": "Globex Facilities Group", "total": 15000.00,
     "issued": date(2026, 8, 5), "lines": [
         ("HVAC overhaul — phase 1", 1, 9500.00),
         ("HVAC overhaul — phase 2", 1, 5500.00)]},
    {"po_number": "PO-2026-114", "vendor": "Northwind Logistics", "total": 9600.00,
     "issued": date(2026, 8, 28), "lines": [          # split-PO target (E3)
         ("Freight services — September leg", 1, 4800.00),
         ("Freight services — October leg", 1, 4800.00)]},
    {"po_number": "PO-2026-118", "vendor": "Globex Facilities Group", "total": 8200.00,
     "issued": date(2026, 9, 1), "lines": [           # tolerance-breach target (E4)
         ("Office lighting retrofit", 40, 175.00),
         ("Installation labour", 8, 150.00)]},
    {"po_number": "PO-2026-121", "vendor": "Foxtrot Media Labs", "total": 5400.00,
     "issued": date(2026, 8, 25), "lines": [          # scanned-invoice target (E1)
         ("Q3 campaign analytics retainer", 3, 1800.00)]},
    {"po_number": "PO-2026-124", "vendor": "Initech Systems", "total": 6750.00,
     "issued": date(2026, 9, 1), "lines": [           # missing-fields target (B1)
         ("Server rack migration — labour", 45, 150.00)]},
    {"po_number": "PO-2026-127", "vendor": "Hooli Cloud Services", "total": 7500.00,
     "issued": date(2026, 8, 30), "lines": [          # line-mismatch target (B2)
         ("Cloud hosting — dedicated nodes", 100, 45.00),
         ("Premium support plan", 1, 3000.00)]},
    {"po_number": "PO-2026-131", "vendor": "Umbrella Facilities Corp", "total": 4900.00,
     "issued": date(2026, 9, 3), "lines": [           # unapproved vendor
         ("Deep cleaning — HQ floors", 1, 4900.00)]},
]


def seed_reference(db: Session) -> None:
    if db.query(Vendor).count():
        return
    by_name = {}
    for v in VENDORS:
        vendor = Vendor(name=v["name"], tax_id=v["tax_id"], approved=v["approved"])
        db.add(vendor)
        by_name[v["name"]] = vendor
    db.flush()  # assign vendor PKs before POs reference them
    for p in POS:
        po = PO(po_number=p["po_number"], vendor_id=by_name[p["vendor"]].id,
                total=p["total"], issued=p["issued"],
                status=p.get("status", "open"))
        db.add(po)
        db.flush()
        for desc, qty, price in p["lines"]:
            db.add(POLine(po_id=po.id, description=desc, qty=qty, unit_price=price))
    db.commit()


def _wipe_runs(db: Session) -> None:
    db.query(StageEvent).delete()
    db.query(Extraction).delete()
    db.query(Match).delete()
    db.query(InvoiceSeen).delete()
    db.query(Run).delete()
    db.commit()


def seed_if_empty(db: Session) -> None:
    seed_reference(db)


def reseed(db: Session) -> dict:
    _wipe_runs(db)
    # reference data may already exist; reseed vendors/POs only if empty
    seed_reference(db)
    return {"vendors": db.query(Vendor).count(), "pos": db.query(PO).count()}
