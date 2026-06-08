#!/usr/bin/env bash
set -euo pipefail

AI_CONTAINER="${AI_CONTAINER:-subway_ai_model}"
ES_URL="${ELASTICSEARCH_URL:-http://subway_es:9200}"
LOG_INDEX_PATTERN="${LOG_INDEX_PATTERN:-subway-logs-*}"
ANOMALY_INDEX="${ANOMALY_INDEX:-subway-anomaly-results}"
LOOKBACK_MINUTES="${LOOKBACK_MINUTES:-30}"
ANALYSIS_MODE="${ANALYSIS_MODE:-rules}"

docker exec \
  -e ELASTICSEARCH_URL="$ES_URL" \
  -e LOG_INDEX_PATTERN="$LOG_INDEX_PATTERN" \
  -e ANOMALY_INDEX="$ANOMALY_INDEX" \
  -e LOOKBACK_MINUTES="$LOOKBACK_MINUTES" \
  -e ANALYSIS_MODE="$ANALYSIS_MODE" \
  "$AI_CONTAINER" \
  python -c 'from main import run_once; run_once()'
