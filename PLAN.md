# ClearMatch — Invoice-to-PO Matching with Explainable Decisions

**Zamp AI Solutions Associate · Case Study 2026 · PS-1 (Finance/AP)**
**Owner:** Santosh Kumar · **Day 1:** Sat 2026-09-19 · **Submit by:** Fri 2026-09-25

---

## 1. Executive summary

ClearMatch is a working automated AP process. It takes a vendor invoice PDF as input, runs it through a seven-stage pipeline — receive → classify → extract → validate → match → decide → report — and produces a **reasoned, explainable decision**: `AUTO-APPROVE`, `NEEDS REVIEW`, or `REJECT`, with reason codes, a confidence score, a plain-English explanation, and a recommended next action. Every stage is visible live as it executes; every run lands in a dashboard with full history, status, and outputs.

What the evaluators see:

- **A live run view** — stages streaming in real time as an invoice is processed.
- **A dashboard** — all runs, decision mix, drill into any run's invoice-vs-PO comparison and reasoning.
- **Deliberate edge cases** — scanned image invoice, duplicate submission, split PO, tolerance breach (+ missing-fields and line-item mismatch handled as bonus coverage).
- **A 5-minute Loom** walking the happy path + two edge cases, narrating the decisions.

## 2. Locked decisions (from the grilling sessions)

| # | Decision | Choice | Why |
|---|----------|--------|-----|
| D1 | Problem statement | **PS-1 Invoice processing** | Self-contained (we generate all test data), zero live-web dependency, richest explainability story, directly matches what Zamp grades on |
| D2 | Stack | **FastAPI backend + Next.js frontend** | UI is explicitly graded (live run view + dashboard); custom app gives both, plus deterministic live demo |
| D3 | Hosting | **Vercel (frontend) + Railway (backend + Postgres)**, Render as fallback | Free tiers, clickable live link for Day 7 and the interview |
| D4 | AI provider | **OpenAI** (gpt-4o-mini class, vision-capable) | One code path handles digital text and scanned images via structured outputs |
| D5 | Decision output | **3-way decision + reason codes + confidence + explanation + recommended next action** | Answers "a clear, reasoned decision" head-on |
| D6 | Edge cases | **Scanned invoice, duplicate, split PO, tolerance breach** (+ missing fields, line mismatch as bonus) | Covers every axis the brief names: messy formats, procurement rules |
| D7 | Input surface | **Drag-drop upload + one-click preset buttons** | Bulletproof live demo; email ingest stated as an assumption |
| D8 | Test data locale | **USD, US-style sales tax** | Neutral for a US evaluation panel |
| D9 | Naming/infra defaults | App: **ClearMatch** · public GitHub repo · Loom free | Simple, professional, no secrets in repo (key lives in Railway env) |

## 3. Assumptions log (state these in the video and interview)

The FAQ says ambiguity is part of the exercise — make an assumption, note it, move on. These are ours:

1. **Ingest:** in production this front-ends an email inbox watcher (invoices arrive as PDF attachments). For the case study, upload + presets replace the inbox.
2. **Procurement system:** represented as a read-only PO reference dataset seeded in the app. We never write back to it.
3. **Tolerances:** 2% or $25 (whichever is greater) soft tolerance; 5% hard cap. Configurable in `config.py` — mirrors common AP practice.
4. **Currency/entity:** single entity, USD, US sales tax.
5. **Human-in-the-loop:** `AUTO-APPROVE` queues the invoice into a payment batch; a human still releases the batch. We automate the *decision*, not the money movement.
6. **Duplicate detection** is by (vendor, invoice number) across prior runs, mirroring an AP system's invoice register.

## 4. Problem framing

A mid-size company gets hundreds of vendor invoice PDFs monthly. An AP analyst opens each, hunts the PO spreadsheet, eyeballs the numbers, and decides. ClearMatch automates that judgment and — critically — keeps the audit trail the analyst's inbox never had.

**Persona we build for:** an AP analyst who needs to trust the decision, see *why* in one glance, and only touch the exceptions.

## 5. Process map (design before build, per the guidance)

```
                     ┌─────────────────────────────────────────────────────────┐
                     │                      CLEARMATCH PIPELINE                │
                     └─────────────────────────────────────────────────────────┘

 email attachment ──▶ 1 RECEIVE      file accepted · checksum · mime/size checks
 (case study:          2 CLASSIFY     text-layer heuristics → DIGITAL vs SCANNED
 upload/preset)        3 EXTRACT      SCANNED → vision model OCR
                                     DIGITAL  → text model (pdfplumber text + LLM
                                     structured output; regex fallback if API down)
                       4 VALIDATE    required fields present? formats sane?
                                    arithmetic self-consistency (Σlines = subtotal,
                                    subtotal + tax = total)
                       5 MATCH       find PO by explicit ref; else vendor+amount+
                                    date-window heuristic · remaining-balance aware
                                    (split POs) · duplicate check vs invoice register
                       6 DECIDE      deterministic rule engine →
                                    decision + reason codes + confidence +
                                    explanation + next action
                       7 REPORT      persist run · stage log · dashboard update

                                     ┌───────────── outputs ─────────────┐
                                     │ decision    reason codes          │
                                     │ confidence  explanation (EN)      │
                                     │ invoice⇄PO diff table             │
                                     │ recommended next action           │
                                     └───────────────────────────────────┘
```

Every stage emits a timestamped event (SSE) that the live run view renders as it happens — the interviewer watches the process think.

## 6. Decision engine specification

### 6.1 Reason codes

| Code | Stage | Meaning |
|------|-------|---------|
| `EXTRACTION_OK` | extract | All fields extracted from digital text layer |
| `EXTRACTION_DEGRADED_OCR` | extract | Scanned image — vision-OCR path, lower field confidence |
| `EXTRACTION_FALLBACK` | extract | LLM unavailable — deterministic regex extractor used |
| `MISSING_TOTAL` | validate | No readable invoice total — decision cannot be amount-based |
| `MISSING_INVOICE_NUMBER` | validate | No invoice number on document |
| `MISSING_PO_REFERENCE` | validate | No explicit PO reference |
| `MISSING_INVOICE_DATE` | validate | No invoice date |
| `ARITHMETIC_MISMATCH` | validate | Line items / subtotal / tax / total don't reconcile |
| `PO_NOT_FOUND` | match | No PO matched by ref or heuristic |
| `VENDOR_NOT_APPROVED` | match | Vendor not in approved vendor master |
| `DUPLICATE_INVOICE_NUMBER` | match | (vendor, invoice number) already seen in a prior run |
| `PO_MATCHED_EXACT` | match | Invoice total == PO remaining amount exactly |
| `PO_MATCHED_WITHIN_TOLERANCE` | match | Within 2% / $25 soft tolerance |
| `PO_AMOUNT_EXCEEDED` | match | Over PO remaining by > soft tolerance |
| `PO_HARD_CAP_EXCEEDED` | match | Over by > 5% hard cap |
| `PO_FULLY_INVOICED` | match | PO already fully consumed by prior invoices |
| `SPLIT_PO_PARTIAL` | match | Invoice consumes part of a PO's remaining balance |
| `PO_LINE_PRICE_MISMATCH` | match | Line-item unit price deviates > 10% from PO line |

### 6.2 Decision matrix

| Decision | Conditions (all evaluated on the validated extraction + match result) |
|----------|---------------------------------------------------------------------|
| **AUTO-APPROVE** | No duplicate · PO matched exact or within soft tolerance · no arithmetic mismatch · all critical fields present · composite confidence ≥ 0.85 |
| **NEEDS REVIEW** | Any of: soft-tolerance breach (≤ hard cap) · degraded OCR with confidence 0.60–0.85 · line price mismatch ≤ 20% · missing non-critical fields · fallback extraction used |
| **REJECT** | Any of: duplicate invoice number · PO not found *and* no PO reference to investigate · hard cap exceeded · PO fully invoiced · vendor not approved |

### 6.3 Confidence model

Composite = weighted blend: extraction confidence (per-field self-reported by the LLM, or 0.95 for regex-verified digital fields), match quality (1.0 exact · 0.9 within tolerance · 0.7 heuristic match), and document quality (0.95 digital · 0.75 scanned). Weights in `config.py`; the number is surfaced with the decision and in the explanation — never a black-box score.

### 6.4 Recommended next actions (per reason code)

`DUPLICATE_INVOICE_NUMBER` → "Reject and notify vendor of prior payment." · `PO_NOT_FOUND` → "Route to AP lead to request PO reference from vendor." · `PO_AMOUNT_EXCEEDED` → "Request credit note or corrected PO from procurement." · etc. The decision payload always tells the human what to do next.

## 7. Edge cases (the graded ones) + bonus coverage

| # | Edge case | Input | Expected behavior — what it reveals |
|---|-----------|-------|-------------------------------------|
| E1 | **Scanned invoice** | Image-only PDF, slight rotation/noise, no text layer | Classify→SCANNED, vision-OCR extraction, `EXTRACTION_DEGRADED_OCR`, confidence drops; if fields still reconcile to PO within tolerance → NEEDS REVIEW (not silent auto-approve). Shows format-messiness handling |
| E2 | **Duplicate submission** | Same vendor + invoice number as an earlier run, different total | `DUPLICATE_INVOICE_NUMBER` → REJECT, run detail links to the prior run. Shows payment-fraud guardrail |
| E3 | **Split PO** | Two invoices (INV-1041-A, -B), each 50% of one PO | First: `SPLIT_PO_PARTIAL` + AUTO-APPROVE against remaining balance. Second: matches the *remaining* $X, not the PO total. Shows remaining-balance-aware matching |
| E4 | **Tolerance breach** | Total 4% over PO (between soft 2% and hard 5%) | `PO_AMOUNT_EXCEEDED` → NEEDS REVIEW with explanation "invoice exceeds PO remaining balance by $Y (4.0%); soft tolerance 2%". Shows judgment, not brittleness |
| B1 | *Bonus:* missing fields | No invoice number, no PO ref | Not a crash — pending-style NEEDS REVIEW with "what's needed from vendor" output |
| B2 | *Bonus:* line-item mismatch | Unit price 10–15% off PO line | `PO_LINE_PRICE_MISMATCH` caught by line-level check even though totals can be engineered to pass |

E1–E4 get one-click preset buttons and rehearsal time. B1/B2 are wired and shown in the dashboard, not rehearsed — a process that handles 3 scenarios well beats one that half-handles ten.

## 8. Test data design (all self-generated, per FAQ)

### 8.1 Vendor + PO dataset (seeded, ~6 vendors / ~12 POs)

Engineered so every scenario has a deterministic landing spot — e.g., `PO-2026-114` (Northwind Logistics, $9,600.00) exists *only* to be split by E3; `PO-2026-118` exists to be breached by E4. Includes one unapproved vendor for the vendor-master check.

### 8.2 Invoice suite (generated PDFs, committed to repo under `testdata/`)

| File | Path | Scenario |
|------|------|----------|
| `inv_happy_acme.pdf` | digital text, exact match | happy path |
| `inv_scanned_foxtrot.pdf` | rendered image→PDF (PIL: rotation + noise), no text layer | E1 |
| `inv_duplicate_acme.pdf` | same invoice number as happy, different total | E2 |
| `inv_split_a.pdf` / `inv_split_b.pdf` | 50% + 50% of PO-2026-114 | E3 |
| `inv_breach_globex.pdf` | total 4% over PO | E4 |
| `inv_missing_initech.pdf` | no invoice number, no PO ref | B1 |
| `inv_linemismatch_hooli.pdf` | line unit price 12% over PO line | B2 |

Generator scripts (`tools/make_pos.py`, `tools/make_invoices.py`) are part of the repo — the evaluator can see exactly how inputs were made, and we can regenerate deterministically.

## 9. Architecture

```
┌────────────────────┐        ┌──────────────────────────────────────┐
│  Next.js (Vercel)  │  SSE   │        FastAPI (Railway)             │
│  /        run view ├───────▶│  POST /api/runs      upload→run      │
│  /dashboard        │        │  GET  /api/runs       history        │
│  /runs/[id] detail │        │  GET  /api/runs/{id}  full detail    │
└────────────────────┘        │  GET  /api/runs/{id}/events (SSE)    │
                              │  GET  /api/health · /api/pos · /seed │
                              │                                      │
                              │  pipeline/  7 stages, event emitter  │
                              │  engine/     match + decide (pure)   │
                              │  extractors/ digital · vision · fallback │
                              │  db/         SQLAlchemy → Postgres   │
                              └──────────────┬───────────────────────┘
                                             │ structured outputs
                                             ▼
                                    OpenAI (gpt-4o-mini, vision)
```

Key engineering choices:

- **The decision engine is pure Python, no LLM.** LLM does perception (extraction); rules do judgment. This is deliberate and is a talking point: deterministic, auditable decisions; the LLM never "decides."
- **Deterministic fallback extractor** (pdfplumber + regex) if the OpenAI call fails/times out (60s) → `EXTRACTION_FALLBACK`, decision downgrades to NEEDS REVIEW at most. The process degrades gracefully instead of erroring — demo-day insurance.
- **Runs execute in a background task**; the UI subscribes via SSE per-run and sees each stage event as it's emitted.
- **SQLite locally, Postgres on Railway** — same SQLAlchemy models.
- **Preset endpoint** serves the committed test PDFs so the one-click demo buttons always run the exact rehearsed inputs.

## 10. Data model

```
vendors(id, name, tax_id, approved)
pos(id, po_number, vendor_id, total, currency, status[open|closed], issued)
po_lines(id, po_id, description, qty, unit_price)
runs(id, filename, sha256, mime, size, decision, confidence, reason_codes[],
     explanation, next_action, po_id, created_at, duration_ms)
extractions(id, run_id, source[text|ocr|fallback], raw json, field_confidence json)
matches(id, run_id, po_id, method[ref|heuristic], invoice_total, po_remaining,
        delta_abs, delta_pct)
events(id, run_id, stage, status, message, data json, ts)   ← stage log / SSE feed
invoices_seen(vendor_name, invoice_number, run_id)          ← duplicate register
```

## 11. UI design

Design language: clean fintech — white/neutral canvas, one strong accent (deep blue), monospace for numbers, green/amber/red semantic chips for decisions. Density over decoration.

- **`/` Run view** — drag-drop zone, preset buttons (Happy · E1–E4), and the live stage stream: seven stages lighting up in order with per-stage payloads (extraction JSON, match table, reason chips) as they land.
- **`/dashboard`** — runs table (time, vendor, total, decision chip, reason codes), decision-mix summary cards, click-through to detail.
- **`/runs/[id]`** — the money screen: extracted invoice fields ⇄ PO side-by-side with per-field delta highlighting, confidence bar, reason-code chips, plain-English explanation, recommended next action, full stage timeline.

## 12. Repo structure

```
clearmatch/
├── PLAN.md  README.md
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  db.py
│   │   ├── models.py  schemas.py
│   │   ├── routers/(runs.py reference.py health.py)
│   │   ├── pipeline/(runner.py stages.py events.py)
│   │   ├── engine/(matching.py decision.py confidence.py)
│   │   └── extractors/(digital.py vision.py fallback.py llm.py)
│   ├── tests/(test_matching.py test_decision.py test_validate.py)
│   ├── tools/(seed_db.py make_pos.py make_invoices.py)
│   └── requirements.txt
├── frontend/               # Next.js (App Router, TS, Tailwind)
└── testdata/               # generated PO dataset + invoice PDFs (committed)
```

## 13. Build schedule (≈3–4 h/day)

| Day | Date | Scope | Done when |
|-----|------|-------|-----------|
| 1 | Sat 09-19 | **(this plan)** · reply "ASA Case Study — Santosh Kumar — PS-1" to coordinator · repo init | email sent, plan committed |
| 2 | Sun 09-20 | Backend scaffold · vendor/PO seed · invoice+scan generators · digital extraction happy path | `pytest` green, happy-path invoice extracts correctly |
| 3 | Mon 09-21 | Matching (ref + heuristic + remaining-balance) · decision engine, all reason codes · unit tests | all edge cases produce correct decisions in tests |
| 4 | Tue 09-22 | Vision/OCR path · fallback extractor · SSE stage events · run-detail API | curl end-to-end on E1–E4 returns reasoned decisions |
| 5 | Wed 09-23 | Next.js UI: run view, dashboard, run detail | full flow click-through locally |
| 6 | Thu 09-24 | Deploy Railway + Vercel · presets · harden (timeouts, error states, CORS) · rehearse demo twice | live URL runs E1–E4 cleanly |
| 7 | Fri 09-25 | Record Loom (≤5:00, 2–3 takes) · submit both links | email to coordinator |

Slippage rule: cut dashboard analytics first, never edge cases. A working process with 3 great scenarios beats a pretty 80%.

## 14. Demo video script (Loom, 5:00)

- **0:00–0:30** — The problem: hundreds of messy invoice PDFs vs a PO spreadsheet; tired-human-on-Friday mistakes. One line on what ClearMatch is.
- **0:30–1:00** — Stack in two sentences: FastAPI pipeline, LLM for perception only, deterministic rules for judgment — every decision auditable. Show the dashboard.
- **1:00–2:15** — **Happy path live.** Upload clean invoice; narrate the seven stages as they stream; land on AUTO-APPROVE; show the invoice⇄PO diff and explanation.
- **2:15–3:00** — **E1 scanned invoice:** same pipeline, classify flips to SCANNED, OCR path, confidence drops, NEEDS REVIEW — deliberate, not failure.
- **3:00–3:45** — **E2 duplicate** (or E3 split PO if it demos better in rehearsal): REJECT with link to prior run / remaining-balance match.
- **3:45–4:30** — Dashboard: history, decision mix, drill into the tolerance-breach run and its reasoning.
- **4:30–5:00** — Judgment calls: why LLM never decides, tolerance design, what I'd build next (email ingest, PO write-back, batch release workflow).

## 15. Live interview runbook

1. Open the deployed URL fresh; `/api/health` green (ping it 10 min early to shake off free-tier cold start).
2. Run order: happy → E1 scanned → E3 split (run A, then B — the remaining-balance flip is the showpiece) → E2 duplicate → dashboard drill.
3. Have `POST /api/seed/reset` ready to restore demo state if the interviewer wants a rerun.
4. Backup: local instance running in a second tab in case of network issues.
5. Expected questions & one-line answers: *Why rules over LLM for the decision?* Auditable + deterministic; LLM variance has no place in a payment decision. *How would this scale?* Pipeline stages are stateless workers; SSE→queue for fan-out. *What's missing?* Email ingest, PO write-back, batch payment release, multi-currency.

## 16. Risk register

| Risk | Mitigation |
|------|-----------|
| OpenAI latency/outage mid-demo | 60s timeout → deterministic fallback extractor; presets are pre-verified; worst case decision downgrades, never errors |
| Free-tier cold start on the live link | Ping health endpoint before interview; backup local tab |
| Vision-OCR field variance on scanned invoice | Normalization + fuzzy number parsing; preset PDF pre-tested; E1's expected outcome is NEEDS REVIEW so a wobble in confidence doesn't break the story |
| Scope creep | Day-plan above; cut dashboard analytics first, never edge cases |
| Demo breakage live | Preset buttons + seed reset; rehearsed run order; second browser tab backup |
| Runway: not done by Day 6 | Ship happy path + 2 edge cases deployed > perfect 4 undeployed (their guidance #5) |

## 17. Security & abuse posture (public demo URL)

Architecture is the first control: **the LLM never decides** — model output only fills a schema that feeds the deterministic rule engine, so prompt injection in an invoice can at most produce a bad *extraction*, which tolerance/duplicate/arithmetic rules still bound (OWASP LLM01/LLM05). Model output is sanitized at the single parse choke point: non-finite/negative numbers → null, strings length-capped. Uploads are magic-byte-checked (`%PDF`), size-capped (10 MB), page-capped (50, parser-bomb guard), and filenames sanitized before storage/reflection. LLM-calling endpoints are rate-limited per IP (60/h). `/api/seed/reset` is optionally gated by `RESET_TOKEN` (set it in Railway env). SSE streams self-close after 120 s. SQL is ORM-parameterized throughout; no secrets in code (key via env); security headers (nosniff, DENY, no-referrer) set app-wide. Deliberately open, documented trade-offs: no auth (anonymous read/run demo by design; no cookies so wildcard CORS is harmless), per-process rate limiter (single-dyno demo scale). Talking point: security choices were threat-modeled, not bolted on.

## 18. Rubric self-check

| They grade | We cover |
|------------|----------|
| Process actually runs, real input → real output | PDF in, decision + audit trail out, live |
| Intuitive UI: live run view | `/` — seven stages streaming via SSE |
| Dashboard: history, status, outputs | `/dashboard` + `/runs/[id]` |
| Edge cases handled deliberately | E1–E4 rehearsed + B1/B2 wired |
| Explainable decisions | reason codes + confidence + English explanation + next action |
| Judgment behind design choices | §6 rules, §3 assumptions, §14–15 narration |
| 5-min video + live link | §13 Day 7, §14 script |
