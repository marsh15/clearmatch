# Demo script: Loom (5:00) and live interview runbook

Record standing up, screen at 100% zoom, cursor calm. One take is fine;
two max. Read this as a teleprompter. The timings assume the LLM path with
the key set. If OpenAI is slow, narrate the wait ("the vision model is
reading the scan"); the live stage stream fills the silence.

---

## 0:00-0:30: The problem (dashboard on screen)

> "This is ClearMatch. The problem it solves: a mid-size company gets
> hundreds of vendor invoice PDFs a month. Today a person opens each one,
> hunts down the purchase order, eyeballs the numbers, and decides what to
> do. I automated that decision, end to end, with the reasoning visible."

Click Dashboard: "Every run lands here with its verdict, confidence, and
reason codes. Let me run one live."

## 0:30-2:15: Happy path, live (Run page)

Click **Happy path**. As stages light up, narrate each:

> "Seven stages. Receive: checksum, size, file identity. Classify: this one
> has a text layer, so it's digital. Extract: the LLM reads it into a strict
> schema (vendor, invoice number, lines, totals) and does nothing else; it's
> perception. Validate: did the document add up, are critical fields present.
> Match: invoice PO-2026-101 by explicit reference, against the PO's
> remaining balance, 12,000 dollars even. Decide: deterministic rules, not
> the model. Exact match, no duplicate, confidence 0.95. AUTO-APPROVE,
> queued for the payment batch. A human still releases the batch."

Open the run detail: "Side by side: what was extracted versus what the PO
says. Delta zero. Full stage timeline underneath. This is the audit trail
the spreadsheet never had."

## 2:15-3:00: Edge case E1, scanned invoice

Click **E1, Scanned**.

> "Same pipeline, but classify catches it: no text layer, this is a scan.
> Extraction switches to a vision model, OCR. Confidence drops by design.
> The numbers still match the PO, but a degraded read never auto-approves:
> NEEDS REVIEW, and the next action tells the analyst to eyeball the
> original. The degradation is visible, not hidden."

## 3:00-3:50: Edge case E3, split PO (run A then B)

Click **E3, Split A**.

> "Northwind splits one 9,600-dollar PO into two invoices. Invoice A is
> 4,800 against a 9,600 remaining balance. Note the matching is
> remaining-balance aware, and tolerance is one-sided: a partial draw is
> legitimate, over-billing is not. SPLIT_PO_PARTIAL, auto-approved."

Click **E3, Split B**.

> "Invoice B now matches exactly what's *left*: 4,800. PO_MATCHED_EXACT.
> Only approved invoices consume the balance; anything less leaves it
> untouched."

## 3:50-4:30: E2 duplicate, then dashboard drill

Click **E2, Duplicate**.

> "Someone resubmits the Acme invoice with the same number, 400 dollars
> more. The duplicate register catches it: REJECT, and the run links back to
> the original. That's a payment-fraud guardrail."

Back to Dashboard: "Decision mix across all runs, drill into any run's
reasoning. Tolerance breaches (four percent over PO) land in review with a
recommended action, not a silent pass or fail."

## 4:30-5:00: Judgment calls, and what's next

> "Three decisions worth defending. The LLM never decides: extraction is
> perception, judgment is deterministic rules, so every decision is
> auditable and a prompt-injected invoice can't talk its way past the
> tolerance check. If OpenAI goes down, a deterministic fallback extracts
> and the ceiling drops to NEEDS REVIEW; the process degrades, it never
> breaks. And the UI is the process: every stage you saw execute is an
> event the backend streamed live.
> What I'd build next: email ingest fronting this, PO write-back, and batch
> payment release with maker-checker. Thanks for watching."

---

## Interview live-demo runbook

Order (rehearsed): happy, E1 scanned, E3 A, E3 B, E2 duplicate, dashboard
drill, and optionally the B2 line-mismatch detail page.

- 10 min before: ping the Vercel URL and `/api/health` (cold-start wake).
- Reset state: `POST /api/seed/reset` with the `X-Reset-Token` header.
- Backup tab: local `localhost:3000` running.
- Expected questions:
  - *Why rules over LLM for the decision?* Auditability and determinism.
    Model variance has no place in a payment decision; the LLM's job is
    reading messy documents, which it is uniquely good at.
  - *How does it scale?* The stages are stateless; SSE becomes a queue for
    fan-out; Postgres already carries the audit trail.
  - *What's missing?* Email ingest, PO write-back, multi-currency,
    maker-checker release. One sentence each on how I'd add them.
