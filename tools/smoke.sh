#!/usr/bin/env bash
# End-to-end smoke: run every demo preset against any API base and print
# the decisions. Usage: tools/smoke.sh http://localhost:8000
set -euo pipefail
BASE="${1:-http://localhost:8000}"
echo "smoke against $BASE"
health=$(curl -s -m 90 "$BASE/api/health")
echo "health: $health"
python3 - "$BASE" <<'EOF'
import json, sys, time, urllib.request

base = sys.argv[1]

def post(path):
    req = urllib.request.Request(base + path, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["run_id"]

def get(path):
    with urllib.request.urlopen(base + path, timeout=90) as r:
        return json.load(r)

ok = True
for preset in ["happy", "split_a", "split_b", "breach", "missing",
               "linemismatch", "scanned", "duplicate"]:
    rid = post(f"/api/runs/preset/{preset}")
    run = get(f"/api/runs/{rid}")
    for _ in range(30):
        if run["decision"] != "PENDING":
            break
        time.sleep(1)
        run = get(f"/api/runs/{rid}")
    print(f'{run["filename"]:30} -> {run["decision"]:13} conf={run["confidence"]:<5} '
          f'codes={",".join(run["reason_codes"])}')
EOF
echo "smoke complete"
