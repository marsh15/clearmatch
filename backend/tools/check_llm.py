"""One-shot verification of the real OpenAI extraction path.

Run it yourself with your key (never share the key):
    cd backend
    cp .env.example .env        # paste your key into .env
    set -a; source .env; set +a # or: export OPENAI_API_KEY=sk-...
    ../.venv/bin/python tools/check_llm.py

It runs the actual pipeline on happy (digital) and scanned (vision) invoices
and prints the decisions. Expect: happy -> AUTO-APPROVE, scanned -> NEEDS
REVIEW (EXTRACTION_DEGRADED_OCR). If both lines match, the demo is real.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import Base, SessionLocal, engine
from app.pipeline.runner import run_pipeline
from app.models import Run
from tools.seed_db import reseed

TESTDATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "testdata"))


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not set — put it in backend/.env and source it first.")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    reseed(db)

    for name in ("inv_happy_acme.pdf", "inv_scanned_foxtrot.pdf"):
        with open(os.path.join(TESTDATA, name), "rb") as f:
            blob = f.read()
        run = Run(filename=name, sha256="", size=len(blob))
        db.add(run)
        db.commit()
        run = run_pipeline(db, run.id, name, blob)
        print(f"{name:28} -> {run.decision:13} conf={run.confidence} "
              f"codes={','.join(run.reason_codes)}")
        print(f"  {run.explanation}")
    db.close()


if __name__ == "__main__":
    main()
