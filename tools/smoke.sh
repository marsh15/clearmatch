#!/usr/bin/env bash
# End-to-end smoke: reset demo state, run every demo preset against any API
# base, assert the promised decision for each. Exits non-zero on any mismatch.
#
# Expected decisions follow the README preset table when the backend has an
# OPENAI_API_KEY; on a keyless backend the deterministic fallback extractor
# caps everything at NEEDS REVIEW, and the script asserts that table instead
# (it probes which path is live before judging).
#
# Usage: tools/smoke.sh http://localhost:8000   (backend must have no RESET_TOKEN set)
set -euo pipefail
BASE="${1:-http://localhost:8000}"
echo "smoke against $BASE"
health=$(curl -s -m 90 "$BASE/api/health")
echo "health: $health"
reset=$(curl -s -m 90 -X POST "$BASE/api/seed/reset")
echo "reset: $reset"
python3 - "$BASE" <<'EOF'
import json, sys, time, urllib.request

base = sys.argv[1]

EXPECTED_LLM = {          # README demo table (real extraction path)
    "happy": "AUTO-APPROVE",
    "split_a": "AUTO-APPROVE",
    "split_b": "AUTO-APPROVE",
    "breach": "NEEDS REVIEW",
    "missing": "NEEDS REVIEW",
    "linemismatch": "NEEDS REVIEW",
    "scanned": "NEEDS REVIEW",
    "duplicate": "REJECT",
}
EXPECTED_FALLBACK = {     # no API key: fallback extractor caps at NEEDS REVIEW
    "happy": "NEEDS REVIEW",
    "split_a": "NEEDS REVIEW",
    "split_b": "NEEDS REVIEW",
    "breach": "NEEDS REVIEW",
    "missing": "NEEDS REVIEW",
    "linemismatch": "NEEDS REVIEW",
    "scanned": "REJECT",  # image PDF, nothing to regex -> no anchor -> REJECT
    "duplicate": "REJECT",
}

def post(path):
    req = urllib.request.Request(base + path, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["run_id"]

def get(path):
    with urllib.request.urlopen(base + path, timeout=90) as r:
        return json.load(r)

def run_preset(preset):
    rid = post(f"/api/runs/preset/{preset}")
    run = get(f"/api/runs/{rid}")
    for _ in range(30):
        if run["decision"] != "PENDING":
            break
        time.sleep(1)
        run = get(f"/api/runs/{rid}")
    return run

# probe the extraction path with the first preset before judging anything
probe = run_preset("happy")
keyless = "EXTRACTION_FALLBACK" in probe["reason_codes"]
expected = EXPECTED_FALLBACK if keyless else EXPECTED_LLM
print(f"extraction path: {'fallback (no API key)' if keyless else 'LLM'}")

ok = True
results = [("happy", probe)] + [(p, run_preset(p)) for p in list(expected)[1:]]
for preset, run in results:
    got = run["decision"]
    match = got == expected[preset]
    ok = ok and match
    mark = "ok  " if match else "FAIL"
    print(f'{mark} {preset:13} -> {got:13} (expected {expected[preset]}) '
          f'conf={run["confidence"]:<5} codes={",".join(run["reason_codes"])}')

sys.exit(0 if ok else 1)
EOF
echo "smoke complete"
