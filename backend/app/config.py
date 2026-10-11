"""Central tuning knobs for the ClearMatch pipeline. All thresholds live here so
they can be quoted (and defended) in the demo."""

# Matching tolerances
SOFT_TOLERANCE_PCT = 0.02          # within 2% of PO remaining -> auto-approve territory
SOFT_TOLERANCE_ABS = 25.0          # or within $25, whichever is more generous
HARD_CAP_PCT = 0.05                # beyond 5% -> reject outright
LINE_PRICE_MISMATCH_PCT = 0.10     # line unit price deviating >10% from PO line
HEURISTIC_MATCH_WINDOW_DAYS = 45   # PO issued within this window of invoice date

# Confidence model weights
W_EXTRACTION = 0.5
W_MATCH = 0.3
W_DOC_QUALITY = 0.2

# Doc-quality priors: digital text layer vs vision-OCR vs regex fallback
CONF_DIGITAL = 0.95
CONF_OCR = 0.75
CONF_FALLBACK = 0.70

# Decision thresholds
AUTO_APPROVE_CONFIDENCE = 0.85

# LLM
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TIMEOUT_S = 60

# Upload / abuse guards (public demo URL — see PLAN.md security posture)
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 50
RUN_RATE_LIMIT_PER_HOUR = 60    # LLM-calling endpoints, per client IP
SSE_MAX_SECONDS = 120           # close a stalled run's event stream

# Currency / locale (assumption #4 in PLAN.md)
CURRENCY = "USD"
