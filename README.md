# ClearMatch

Invoice-to-PO matching with explainable decisions — Zamp AI Solutions Associate
case study, PS-1 (Finance/AP). Full design in [PLAN.md](PLAN.md).

A vendor invoice PDF goes in; a reasoned decision comes out — `AUTO-APPROVE`,
`NEEDS REVIEW`, or `REJECT` — with reason codes, a confidence score, a
plain-English explanation, and a recommended next action. Every pipeline stage
(receive → classify → extract → validate → match → decide → report) streams
live into the UI, and every run lands in the dashboard.

**Architecture:** FastAPI backend (pipeline + deterministic decision engine;
the LLM does perception only — it never decides) + Next.js frontend.
SQLite locally, Postgres on Railway.

## Run it locally

```bash
# backend (http://localhost:8000)
cd backend
python3 -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt
../.venv/bin/python -m uvicorn app.main:app --reload

# frontend (http://localhost:3000) — in a second terminal
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev
```

Works with no API key (deterministic fallback extractor; decisions cap at
NEEDS REVIEW). To enable the real LLM path: `cp backend/.env.example
backend/.env`, paste your `OPENAI_API_KEY`, and verify with
`backend/tools/check_llm.py` (run instructions in its docstring).

## Demo presets (one-click, rehearsed)

| Preset | Scenario | Expected |
|--------|----------|----------|
| happy | clean digital invoice, exact PO match | AUTO-APPROVE |
| scanned | image-only PDF, vision-OCR path | NEEDS REVIEW (`EXTRACTION_DEGRADED_OCR`) |
| duplicate | same vendor+invoice number resubmitted | REJECT (`DUPLICATE_INVOICE_NUMBER`) |
| split_a → split_b | one PO, two invoices | AUTO-APPROVE against remaining balance (run A before B) |
| breach | total 4% over PO | NEEDS REVIEW (`PO_AMOUNT_EXCEEDED`) |
| missing | no invoice number / PO ref | NEEDS REVIEW, heuristic match |
| linemismatch | totals agree, unit prices don't | NEEDS REVIEW (`PO_LINE_PRICE_MISMATCH`) |

Reset demo state any time: `POST /api/seed/reset`.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest tests/ -q   # 39 tests
```
