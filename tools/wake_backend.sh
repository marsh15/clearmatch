#!/usr/bin/env bash
# Wake the codespace-hosted demo backend (used only if the backend runs on a
# GitHub Codespace instead of Render). Requires: gh auth with codespace scope.
set -euo pipefail
NAME="clearmatch-api"
gh codespace stop -c "$NAME" 2>/dev/null || true
gh codespace ssh -c "$NAME" -- "cd clearmatch/backend && \
  (../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 \
   > /tmp/api.log 2>&1 & echo started)"
