# Day-7 submission email (fill the two blanks, send)

> **To:** your hiring coordinator
> **Subject:** ASA Case Study — Santosh Kumar — PS-1 — Submission
>
> Hi [Coordinator name],
>
> Submitting my case study for PS-1, invoice processing.
>
> **Working process (live and runnable):** https://clearmatch.vercel.app
> — upload any invoice PDF, or use the one-click demo presets on the Run page
> (the interview demo order is: Happy path, E1 Scanned, E3 Split A then B,
> E2 Duplicate, then the Dashboard). Design decisions, the decision-rule
> matrix, and my assumptions log are in the repo:
> https://github.com/marsh15/clearmatch (PLAN.md).
>
> **5-minute demo video:** [LOOM LINK]
>
> The process takes a PDF through seven visible stages — receive, classify,
> extract, validate, match, decide, report — and outputs an explainable
> decision (AUTO-APPROVE / NEEDS REVIEW / REJECT) with reason codes,
> confidence, and a recommended next action. The LLM does extraction only;
> every payment decision is made by deterministic, auditable rules.
>
> Looking forward to walking you through it live.
>
> Best,
> Santosh Kumar

---

## Before sending this email

1. Backend live: Render → New → Blueprint → `marsh15/clearmatch`
   (paste `OPENAI_API_KEY` when prompted). Confirm
   `https://<render-url>/api/health` → `{"status":"ok"}`.
2. If the Render URL is NOT `https://clearmatch-api.onrender.com`, tell the
   agent (or run: `vercel env rm API_BASE_URL production --yes` then
   `printf '%s' 'https://<render-url>' | vercel env add API_BASE_URL production`
   then `vercel --prod --yes` from `frontend/`).
3. Record the Loom following DEMO_SCRIPT.md (5:00, two takes max).
4. Click every preset once on https://clearmatch.vercel.app to confirm the
   live link is warm and correct.
