#!/usr/bin/env bash
set -euo pipefail
BACKEND="${BACKEND:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$BACKEND"
if [ -f "../.venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "../.venv/bin/activate"
fi
export REFRESH_UNIVERSE_MODE="${REFRESH_UNIVERSE_MODE:-sp500}"
python scheduled_refresh.py
