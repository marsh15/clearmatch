#!/usr/bin/env bash
# Bring the demo backend online on a GitHub Codespace — run this on YOUR Mac
# (terminal opens the browser for you; press Enter there once).
# When it finishes it prints the public URL — send that URL back to the agent.
set -euo pipefail
NAME="clearmatch-api"
REPO="marsh15/clearmatch"

echo "==> 1/4 granting the codespace permission (approve in the browser window that opens)"
gh auth refresh -h github.com -s codespace

echo "==> 2/4 creating the codespace (first time takes ~2 min)"
gh codespace create --repo "$REPO" --machine basicLinux32gb --display-name "$NAME" 2>/dev/null \
  || echo "     codespace already exists, continuing"

echo "==> 3/4 installing deps and starting the API"
gh codespace ssh -c "$NAME" -- bash -c '
  cd clearmatch/backend
  if [ ! -x ../.venv/bin/python ]; then python3 -m venv ../.venv; fi
  ../.venv/bin/pip install -q -r requirements.txt
  pkill -f "uvicorn app.main" 2>/dev/null || true
  nohup ../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
  sleep 3
  curl -s http://localhost:8000/api/health
'

echo ""
echo "==> 4/4 making port 8000 public"
gh codespace ports visibility 8000:public -c "$NAME"
gh codespace ports list -c "$NAME"

URL=$(gh codespace ports list -c "$NAME" | awk '/8000/ {print $1}' | head -1)
cat <<EOF

==========================================================
Backend is live at: $URL
Send that URL to the agent — it will connect the frontend,
verify all presets, and hand you the finished demo link.
(It sleeps when idle; wake it any time with
 tools/wake_backend.sh, or move to Render before interview.)
==========================================================
EOF
