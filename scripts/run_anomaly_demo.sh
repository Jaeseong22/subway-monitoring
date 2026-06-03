#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AI_DIR="$ROOT_DIR/ai_service"
PYTHON_BIN="$AI_DIR/.venv/bin/python"
ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
DEMO_INDEX="${DEMO_INDEX:-subway-demo-logs}"
RESULT_INDEX="${ANOMALY_INDEX:-subway-anomaly-results}"
SCENARIO="${1:-}"

usage() {
  cat <<'EOF'
Usage: scripts/run_anomaly_demo.sh <normal|api-failure|traffic-spike|scheduler-failure|restore>

  normal             Insert normal synthetic logs and publish a normal analysis.
  api-failure        Insert detailed API timeout/429 failures and publish a critical analysis.
  traffic-spike      Insert a traffic saturation scenario and recommend horizontal scaling.
  scheduler-failure  Insert a scheduler failure scenario and publish a critical analysis.
  restore            Analyze current real logs and return the dashboard to live status.
EOF
}

require_services() {
  curl -fsS "$ES_URL" >/dev/null
  if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Missing Python environment: $PYTHON_BIN" >&2
    exit 1
  fi
}

put_api_event() {
  local success="$1"
  local elapsed_ms="$2"
  local http_status="$3"
  local error_code="$4"
  local message="$5"
  local timestamp
  timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  curl -fsS -X POST "$ES_URL/$DEMO_INDEX/_doc" \
    -H 'Content-Type: application/json' \
    -d "{\"@timestamp\":\"$timestamp\",\"event_type\":\"API_COLLECTION\",\"api_name\":\"getAllRealtimeArrivals\",\"endpoint\":\"/api/subway/realtimeStationArrival/ALL\",\"success\":\"$success\",\"elapsed_ms\":\"$elapsed_ms\",\"http_status\":\"$http_status\",\"error_code\":\"$error_code\",\"error_msg\":\"$message\",\"message\":\"$message\",\"service_name\":\"subway-demo\"}" \
    >/dev/null
}

put_scheduler_event() {
  local success="$1"
  local error_message="$2"
  local timestamp
  timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  curl -fsS -X POST "$ES_URL/$DEMO_INDEX/_doc" \
    -H 'Content-Type: application/json' \
    -d "{\"@timestamp\":\"$timestamp\",\"event_type\":\"SCHEDULER\",\"scheduler_name\":\"fetchAndSaveArrivalInfo\",\"success\":\"$success\",\"duration_ms\":\"430\",\"error_msg\":\"$error_message\",\"message\":\"$error_message\",\"service_name\":\"subway-demo\"}" \
    >/dev/null
}

put_traffic_event() {
  local request_count="$1"
  local requests_per_second="$2"
  local cpu_percent="$3"
  local memory_percent="$4"
  local queue_depth="$5"
  local minutes_ago="$6"
  local timestamp
  timestamp="$(date -u -v-"$minutes_ago"M '+%Y-%m-%dT%H:%M:%SZ')"
  curl -fsS -X POST "$ES_URL/$DEMO_INDEX/_doc" \
    -H 'Content-Type: application/json' \
    -d "{\"@timestamp\":\"$timestamp\",\"event_type\":\"TRAFFIC\",\"success\":\"true\",\"endpoint\":\"/api/v1/stations/arrivals/all\",\"request_count\":\"$request_count\",\"requests_per_second\":\"$requests_per_second\",\"cpu_percent\":\"$cpu_percent\",\"memory_percent\":\"$memory_percent\",\"queue_depth\":\"$queue_depth\",\"instance_count\":\"1\",\"elapsed_ms\":\"860\",\"message\":\"Traffic saturation sample\",\"service_name\":\"subway-demo\"}" \
    >/dev/null
}

add_metric_event() {
  local timestamp
  timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  curl -fsS -X POST "$ES_URL/$DEMO_INDEX/_doc?refresh=true" \
    -H 'Content-Type: application/json' \
    -d "{\"@timestamp\":\"$timestamp\",\"event_type\":\"METRIC_COLLECTION\",\"success\":\"true\",\"duration_ms\":\"340\",\"up_count\":\"310\",\"down_count\":\"270\",\"fetched_total\":\"2999\",\"line1_saved\":\"580\",\"time_category\":\"RUSH_HOUR\",\"day_of_week\":\"MONDAY\",\"hour_of_day\":\"18\",\"message\":\"Synthetic demo metric\",\"service_name\":\"subway-demo\"}" \
    >/dev/null
}

reset_demo_index() {
  curl -fsS -X DELETE "$ES_URL/$DEMO_INDEX" >/dev/null 2>&1 || true
}

run_analysis() {
  local input_pattern="$1"
  (
    cd "$AI_DIR"
    ELASTICSEARCH_URL="$ES_URL" \
    LOG_INDEX_PATTERN="$input_pattern" \
    ANOMALY_INDEX="$RESULT_INDEX" \
    LOOKBACK_MINUTES=30 \
    ANALYSIS_MODE=rules \
      "$PYTHON_BIN" -c 'from main import run_once; run_once()'
  )
  curl -fsS -X POST "$ES_URL/$RESULT_INDEX/_refresh" >/dev/null
}

require_services

case "$SCENARIO" in
  normal)
    reset_demo_index
    for _ in {1..10}; do
      put_api_event "true" "95" "200" "NONE" "정상 응답"
    done
    put_scheduler_event "true" "정상 수집 완료"
    add_metric_event
    run_analysis "$DEMO_INDEX"
    echo "Demo published: 정상"
    ;;
  api-failure)
    reset_demo_index
    for _ in {1..7}; do
      put_api_event "true" "112" "200" "NONE" "정상 응답"
    done
    put_api_event "false" "5030" "504" "UPSTREAM_TIMEOUT" "서울 실시간 도착 API 응답 대기시간 초과"
    put_api_event "false" "5100" "504" "UPSTREAM_TIMEOUT" "서울 실시간 도착 API 응답 대기시간 초과"
    put_api_event "false" "380" "429" "RATE_LIMITED" "호출 한도 초과 응답"
    put_scheduler_event "true" "수집 작업은 완료됐으나 API 일부 실패"
    add_metric_event
    run_analysis "$DEMO_INDEX"
    echo "Demo published: 위험 (API 오류율 30%)"
    ;;
  traffic-spike)
    reset_demo_index
    for _ in {1..10}; do
      put_api_event "true" "140" "200" "NONE" "정상 응답"
    done
    put_scheduler_event "true" "정상 수집 완료"
    put_traffic_event "280" "460" "72" "68" "34" "10"
    put_traffic_event "410" "720" "88" "79" "121" "5"
    put_traffic_event "560" "970" "96" "86" "318" "0"
    add_metric_event
    run_analysis "$DEMO_INDEX"
    echo "Demo published: 위험 (트래픽 급증 / 수평 확장 권고)"
    ;;
  scheduler-failure)
    reset_demo_index
    for _ in {1..10}; do
      put_api_event "true" "104" "200" "NONE" "정상 응답"
    done
    put_scheduler_event "false" "서울 API 연결 타임아웃으로 수집 배치 중단"
    add_metric_event
    run_analysis "$DEMO_INDEX"
    echo "Demo published: 위험 (스케줄러 장애)"
    ;;
  restore)
    run_analysis "${LIVE_LOG_INDEX_PATTERN:-subway-logs-*}"
    reset_demo_index
    echo "Dashboard restored to live log analysis."
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
