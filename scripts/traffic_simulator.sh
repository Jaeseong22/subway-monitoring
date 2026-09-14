#!/usr/bin/env bash
# -e를 켜지 않는다: 며칠씩 도는 상시 프로세스라 curl 타임아웃 한 번에 전체가
# 죽으면 안 된다. 개별 호출 실패는 각자 `|| true`로 흡수하고 루프는 계속 돈다.
set -uo pipefail

# 실제 backend 엔드포인트를 시간대별 강도로 호출해 golden signals(traffic/latency/
# saturation)를 진짜 코드 경로로 쌓는다. run_anomaly_demo.sh처럼 ES에 로그 문서를
# 직접 꽂는 게 아니라, RequestTrafficMetrics/GoldenSignalsLogger가 실제로 집계한
# 값이 로그로 남으므로 AI 이상탐지가 쓰는 28일 baseline이 자연스럽게 쌓인다.
#
# Usage:
#   scripts/traffic_simulator.sh
#   nohup scripts/traffic_simulator.sh > logs/traffic_simulator.log 2>&1 &
#
# 종료: Ctrl+C 또는 pkill -f traffic_simulator.sh

BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
TICK_SECONDS="${TICK_SECONDS:-10}"

SIM_EMAIL="${SIM_EMAIL:-sim-user@subway-monitoring.local}"
SIM_PASSWORD="${SIM_PASSWORD:-SimUser1234!}"
SIM_NAME="${SIM_NAME:-트래픽 시뮬레이터}"
FAVORITE_STATION_COUNT="${FAVORITE_STATION_COUNT:-3}"
RELOGIN_INTERVAL_HOURS="${RELOGIN_INTERVAL_HOURS:-6}"

SPIKE_MEAN_INTERVAL_HOURS="${SPIKE_MEAN_INTERVAL_HOURS:-8}"
SPIKE_DURATION_MIN_MINUTES="${SPIKE_DURATION_MIN_MINUTES:-5}"
SPIKE_DURATION_MAX_MINUTES="${SPIKE_DURATION_MAX_MINUTES:-12}"
SPIKE_MULTIPLIER="${SPIKE_MULTIPLIER:-10}"

TOKEN=""
STATIONS_FILE="$(mktemp)"
HOT_STATIONS_FILE="$(mktemp)"
trap 'rm -f "$STATIONS_FILE" "$HOT_STATIONS_FILE"; echo "[$(date '+%H:%M:%S')] 시뮬레이터 중지"; exit 0' INT TERM

require_services() {
  if ! curl -fsS "$BACKEND_URL/actuator/health/readiness" >/dev/null; then
    echo "backend가 준비되지 않았습니다: $BACKEND_URL" >&2
    exit 1
  fi
  if ! command -v python3 >/dev/null; then
    echo "python3가 필요합니다 (역 목록 JSON 파싱용)." >&2
    exit 1
  fi
}

# 역 목록을 가져와 전체/인기역(앞쪽 일부) 두 파일로 나눈다. 인기역 쪽 비중을 높여
# 실사용처럼 특정 역에 조회가 몰리는 분포를 흉내낸다.
fetch_stations() {
  local json
  json="$(curl -fsS "$BACKEND_URL/api/v1/stations")" || { echo "역 목록 조회 실패" >&2; exit 1; }
  echo "$json" | python3 -c 'import json,sys; [print(s["id"]) for s in json.load(sys.stdin)]' > "$STATIONS_FILE"
  local total
  total=$(wc -l < "$STATIONS_FILE" | tr -d ' ')
  if [[ "$total" -eq 0 ]]; then
    echo "역 목록이 비어 있습니다." >&2
    exit 1
  fi
  head -n "$((total / 5 + 5))" "$STATIONS_FILE" > "$HOT_STATIONS_FILE"
  echo "[$(date '+%H:%M:%S')] 역 목록 로드: 전체 ${total}개, 인기역 $(wc -l < "$HOT_STATIONS_FILE" | tr -d ' ')개"
}

random_line() {
  local file="$1"
  local n
  n=$(wc -l < "$file" | tr -d ' ')
  sed -n "$(( (RANDOM % n) + 1 ))p" "$file"
}

# 테스트 계정을 준비하고 인기역 몇 개를 즐겨찾기로 등록해, 개인화 엔드포인트
# (favorites/station-patterns/arrival-alerts)도 실제 데이터로 응답하게 만든다.
ensure_test_account() {
  local register_body
  register_body="$(python3 -c "import json; print(json.dumps({'name': '$SIM_NAME', 'email': '$SIM_EMAIL', 'password': '$SIM_PASSWORD'}))")"
  curl -fsS -X POST "$BACKEND_URL/api/v1/auth/register" \
    -H 'Content-Type: application/json' -d "$register_body" >/dev/null 2>&1 || true

  local login_body login_response
  login_body="$(python3 -c "import json; print(json.dumps({'email': '$SIM_EMAIL', 'password': '$SIM_PASSWORD'}))")"
  login_response="$(curl -fsS -X POST "$BACKEND_URL/api/v1/auth/login" \
    -H 'Content-Type: application/json' -d "$login_body")" || { echo "테스트 계정 로그인 실패, 개인화 엔드포인트는 건너뜁니다." >&2; TOKEN=""; return; }
  TOKEN="$(echo "$login_response" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("token",""))')"

  if [[ -z "$TOKEN" ]]; then
    echo "로그인 응답에 토큰이 없습니다. 개인화 엔드포인트는 건너뜁니다." >&2
    return
  fi

  local i station_id
  for ((i = 0; i < FAVORITE_STATION_COUNT; i++)); do
    station_id="$(random_line "$HOT_STATIONS_FILE")"
    curl -fsS -X POST "$BACKEND_URL/api/v1/users/me/favorites/$station_id" \
      -H "Authorization: Bearer $TOKEN" >/dev/null 2>&1 || true
  done
  echo "[$(date '+%H:%M:%S')] 테스트 계정 준비 완료: $SIM_EMAIL (즐겨찾기 ${FAVORITE_STATION_COUNT}개)"
}

# 요일/시간대에 따른 기준 요청 수(틱당). 출퇴근 피크에 높고 심야에 낮은,
# 실사용 트래픽과 비슷한 굴곡을 준다.
base_count_for() {
  local hour="$1" is_weekend="$2"
  if [[ "$is_weekend" == "true" ]]; then
    if ((hour >= 11 && hour <= 20)); then echo 6; else echo 2; fi
    return
  fi
  if ((hour >= 7 && hour <= 9)); then echo 10
  elif ((hour >= 18 && hour <= 20)); then echo 12
  elif ((hour >= 10 && hour <= 17)); then echo 5
  elif ((hour >= 21 && hour <= 23)); then echo 3
  else echo 1
  fi
}

hit_endpoint() {
  local roll=$((RANDOM % 100))
  if ((roll < 55)); then
    local pick
    if ((RANDOM % 100 < 70)); then pick="$(random_line "$HOT_STATIONS_FILE")"; else pick="$(random_line "$STATIONS_FILE")"; fi
    curl -fsS -o /dev/null -m 10 "$BACKEND_URL/api/v1/stations/$pick/arrivals" || true
  elif ((roll < 70)); then
    curl -fsS -o /dev/null -m 10 "$BACKEND_URL/api/v1/stations/arrivals/all" || true
  elif ((roll < 80)); then
    curl -fsS -o /dev/null -m 10 "$BACKEND_URL/api/v1/stations" || true
  elif ((roll < 90)); then
    curl -fsS -G -o /dev/null -m 10 "$BACKEND_URL/api/v1/stations/search" --data-urlencode "keyword=역" || true
  else
    if [[ -n "$TOKEN" ]]; then
      local personalized=("/api/v1/users/me/favorites" "/api/v1/users/me/station-patterns?days=30" "/api/v1/users/me/arrival-alerts")
      curl -fsS -o /dev/null -m 10 "$BACKEND_URL${personalized[$((RANDOM % ${#personalized[@]}))]}" \
        -H "Authorization: Bearer $TOKEN" || true
    else
      curl -fsS -o /dev/null -m 10 "$BACKEND_URL/api/v1/stations" || true
    fi
  fi
}

fire_batch() {
  local count="$1" i
  for ((i = 0; i < count; i++)); do
    hit_endpoint &
  done
  wait
}

require_services
fetch_stations
ensure_test_account

echo "[$(date '+%H:%M:%S')] 시뮬레이터 시작 (tick=${TICK_SECONDS}s, spike 평균 주기=${SPIKE_MEAN_INTERVAL_HOURS}h, 배율=${SPIKE_MULTIPLIER}x)"

TICKS_PER_RELOGIN=$(( RELOGIN_INTERVAL_HOURS * 3600 / TICK_SECONDS ))
TICKS_PER_SPIKE_INTERVAL=$(( SPIKE_MEAN_INTERVAL_HOURS * 3600 / TICK_SECONDS ))
tick_counter=0
spike_end_epoch=0

while true; do
  hour="$((10#$(TZ=Asia/Seoul date '+%H')))"
  is_weekend="false"
  [[ "$(TZ=Asia/Seoul date '+%u')" -ge 6 ]] && is_weekend="true"
  now_epoch=$(date +%s)

  in_spike="false"
  if ((now_epoch < spike_end_epoch)); then
    in_spike="true"
  elif ((TICKS_PER_SPIKE_INTERVAL > 0)) && ((RANDOM % TICKS_PER_SPIKE_INTERVAL == 0)); then
    duration_min=$(( SPIKE_DURATION_MIN_MINUTES + RANDOM % (SPIKE_DURATION_MAX_MINUTES - SPIKE_DURATION_MIN_MINUTES + 1) ))
    spike_end_epoch=$(( now_epoch + duration_min * 60 ))
    in_spike="true"
    echo "[$(date '+%H:%M:%S')] 이상 주입: 트래픽 스파이크 시작 (${duration_min}분간 ${SPIKE_MULTIPLIER}배)"
  fi

  count="$(base_count_for "$hour" "$is_weekend")"
  if [[ "$in_spike" == "true" ]]; then
    count=$(( count * SPIKE_MULTIPLIER ))
  fi

  fire_batch "$count"

  if (( tick_counter % 30 == 0 )); then
    echo "[$(date '+%H:%M:%S')] hour=${hour} weekend=${is_weekend} spike=${in_spike} requests=${count}"
  fi

  if (( TICKS_PER_RELOGIN > 0 )) && (( tick_counter > 0 )) && (( tick_counter % TICKS_PER_RELOGIN == 0 )); then
    ensure_test_account
  fi

  tick_counter=$((tick_counter + 1))
  sleep "$TICK_SECONDS"
done
