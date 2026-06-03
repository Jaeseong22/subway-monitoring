#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
AI_DIR="$ROOT_DIR/ai_service"
VENV_DIR="$AI_DIR/.venv"
LOG_FILE="$ROOT_DIR/logs/ai_service.log"
PYTHON_BIN="/usr/bin/python3"

if [[ -x "/usr/local/bin/python3" ]]; then
  PYTHON_BIN="/usr/local/bin/python3"
fi

mkdir -p "$ROOT_DIR/logs"

if [[ -f "$ROOT_DIR/.env" ]]; then
  # Load env vars like OPENAI_API_KEY, RUN_TIMES, etc.
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install -r "$AI_DIR/requirements.txt" >/dev/null

cd "$AI_DIR"
exec "$VENV_DIR/bin/python" main.py >> "$LOG_FILE" 2>&1
