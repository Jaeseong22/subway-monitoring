#!/usr/bin/env bash
set -euo pipefail

# 최종 발표 시연 진행용. 시연 모드 켜기, 이전 조치 정리, 급증 주입, 평소 모드 복귀를
# 명령 하나씩으로 한다. 자세한 순서는 README의 "시연" 절 참고.
#
# Usage:
#   scripts/demo.sh up           시연 모드로 기동 + 이전 조치 정리 + 워커·시뮬레이터 시작
#   scripts/demo.sh spike [분]   실제 백엔드에 약 10배 요청을 보낸다 (기본 8분, 급증이 지표에 잡히는 즉시 분석)
#   scripts/demo.sh anomaly <종류>  이상 종류별 시연 (정기 분석을 멈추고 결과를 고정)
#                                traffic-spike | saturation | latency | api-failure |
#                                scheduler-failure | collection-drop
#   scripts/demo.sh restore      종류별 시연을 끝내고 실제 로그 분석으로 복귀
#   scripts/demo.sh analyze      지금 바로 분석 한 번 실행
#   scripts/demo.sh status       서버 대수, 최근 분석, 최근 조치
#   scripts/demo.sh reset        다음 관람객용 초기화: 급증 중지, 열린 조치 만료, backend 1대
#   scripts/demo.sh normal       워커·시뮬레이터를 끄고 평소 설정·1대로 복귀

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if [[ -f .env ]]; then
  set -a; . ./.env; set +a
fi

ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
ACTION_INDEX="${REMEDIATION_INDEX:-subway-remediation-actions}"
LOG_DIR="$ROOT_DIR/logs"
WORKER_PID="$LOG_DIR/demo_worker.pid"
SIM_PID="$LOG_DIR/demo_simulator.pid"
SPIKE_PID="$LOG_DIR/demo_spike.pid"
DEMO_VERIFY_AFTER_MINUTES="${DEMO_VERIFY_AFTER_MINUTES:-5}"

BASE_FILES=(-f docker-compose.yml -f docker-compose.scale.yml)
DEMO_FILES=("${BASE_FILES[@]}" -f docker-compose.demo.yml)

mkdir -p "$LOG_DIR"

stop_pid() {
  local file="$1"
  if [[ -f "$file" ]]; then
    kill "$(cat "$file")" 2>/dev/null || true
    rm -f "$file"
  fi
}

running() {
  [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null
}

wait_backend() {
  echo "백엔드 준비 대기..."
  for _ in $(seq 1 60); do
    curl -fsS "$BACKEND_URL/actuator/health/readiness" >/dev/null 2>&1 && return 0
    sleep 3
  done
  echo "백엔드가 준비되지 않았습니다: $BACKEND_URL" >&2
  exit 1
}

# 이전 리허설에서 남은 승인 대기·실행 중 조치가 있으면 새 제안이 만들어지지 않는다
# (열린 조치 중복 방지). 시연 시작 전에 전부 만료 처리한다.
reset_actions() {
  local body
  body='{"script":{"source":"ctx._source.status = \"EXPIRED\"; ctx._source.note = \"시연 초기화\"","lang":"painless"},"query":{"terms":{"status.keyword":["PENDING","APPROVED","EXECUTING","EXECUTED"]}}}'
  curl -fsS -XPOST "$ES_URL/$ACTION_INDEX/_update_by_query?refresh=true&conflicts=proceed" \
    -H 'Content-Type: application/json' -d "$body" \
    | python3 -c 'import json,sys; print("열린 조치 정리:", json.load(sys.stdin).get("updated", 0), "건")' \
    || echo "조치 인덱스가 아직 없습니다 (정리할 것 없음)"
}

# 급증 폭과 서버별 요청 분산을 보여주는 Kibana 대시보드(kibana/demo-dashboard.ndjson).
# 골든시그널 숫자 필드는 문자열로 색인돼 있어, 데이터 뷰의 런타임 필드(*_num)로 숫자로 바꿔 그린다.
import_kibana_dashboard() {
  curl -fsS -XPOST "$KIBANA_URL/api/saved_objects/_import?overwrite=true" -H 'kbn-xsrf: true' \
    --form file=@kibana/demo-dashboard.ndjson >/dev/null \
    && echo "Kibana 시연 대시보드를 불러왔습니다." \
    || echo "Kibana 대시보드를 불러오지 못했습니다 ($KIBANA_URL)" >&2
}

cmd_up() {
  docker compose "${DEMO_FILES[@]}" up -d --scale backend=1
  wait_backend
  reset_actions

  if ! running "$WORKER_PID"; then
    REMEDIATION_EXECUTE=true \
    REMEDIATION_VERIFY_AFTER_MINUTES="$DEMO_VERIFY_AFTER_MINUTES" \
    REMEDIATION_POLL_SECONDS=10 \
    REMEDIATION_COMPOSE_FILES=docker-compose.yml,docker-compose.scale.yml,docker-compose.demo.yml \
    ELASTICSEARCH_URL="$ES_URL" \
      nohup ai_service/.venv/bin/python ai_service/remediation_worker.py \
      >> "$LOG_DIR/demo_worker.log" 2>&1 &
    echo $! > "$WORKER_PID"
  fi
  if ! running "$SIM_PID"; then
    nohup scripts/traffic_simulator.sh >> "$LOG_DIR/demo_simulator.log" 2>&1 &
    echo $! > "$SIM_PID"
  fi
  import_kibana_dashboard
  echo "시연 모드: 분석 1분 주기, 확장 후 ${DEMO_VERIFY_AFTER_MINUTES}분 뒤 검증"
  echo "그래프: ${KIBANA_URL}/app/dashboards#/view/demo-traffic-scale"
  echo "워커 로그: logs/demo_worker.log  /  급증 주입: scripts/demo.sh spike"
}

cmd_spike() {
  local minutes="${1:-8}"
  if running "$SPIKE_PID"; then
    echo "이미 급증 주입 중입니다." >&2
    exit 1
  fi
  # 시뮬레이터를 1초 간격으로 하나 더 띄우면 평소(10초 간격)의 약 10배가 된다.
  TICK_SECONDS=1 SPIKE_MEAN_INTERVAL_HOURS=0 \
    nohup scripts/traffic_simulator.sh >> "$LOG_DIR/demo_spike.log" 2>&1 &
  local pid=$!
  echo "$pid" > "$SPIKE_PID"
  # reset 뒤 새 급증을 넣었을 수 있으므로 자기 PID가 적힌 경우에만 파일을 지운다.
  (sleep "$((minutes * 60))"; kill "$pid" 2>/dev/null
   [[ "$(cat "$SPIKE_PID" 2>/dev/null)" == "$pid" ]] && rm -f "$SPIKE_PID") >/dev/null 2>&1 &
  local started
  started="$(date -u '+%Y-%m-%dT%H:%M:%S')"
  echo "$(date '+%H:%M:%S') 급증 시작 (${minutes}분간)"
  # 시연 모드에서 골든시그널은 5초마다 남는다. 급증이 담긴 첫 기록이 들어오는 즉시
  # 분석한다(정기 1분 주기를 기다리지 않는다). 보통 5초 안에 시작한다.
  wait_spike_recorded "$started"
  echo "$(date '+%H:%M:%S') 분석 시작 — 확장 제안까지 기다리세요 (scripts/demo.sh status)"
  analyze_now >> "$LOG_DIR/demo_analyze.log" 2>&1 &
}

# 급증 시작 이후 기록된 골든시그널 중 인스턴스당 초당 요청이 평소(약 1.2)보다 확실히 높은 것이
# 나타날 때까지 0.5초 간격으로 확인한다. 10초가 지나도 없으면 그냥 분석한다.
wait_spike_recorded() {
  local since="$1"
  python3 - "$ES_URL" "$since" <<'PY'
import json, sys, time, urllib.request
es, since = sys.argv[1], sys.argv[2]
query = {"size": 0, "query": {"bool": {"filter": [
    {"term": {"event_name.keyword": "golden_signals_summary"}},
    {"term": {"instance_role.keyword": "api"}},
    {"range": {"@timestamp": {"gt": since}}},
    {"script": {"script": "def v = doc['requests_per_second.keyword']; "
                          "return v.size() > 0 && Double.parseDouble(v.value) >= 4.0"}}]}}}
deadline = time.time() + 10
while time.time() < deadline:
    req = urllib.request.Request(f"{es}/subway-logs-*/_search", data=json.dumps(query).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            if json.load(resp)["hits"]["total"]["value"] > 0:
                sys.exit(0)
    except Exception:
        pass
    time.sleep(0.5)
print("급증 기록을 10초 안에 찾지 못했습니다. 그대로 분석합니다.", file=sys.stderr)
PY
}

analyze_now() {
  docker exec subway_ai_model python -c 'import logging; logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s"); from main import run_once; run_once()' 2>&1 \
    | grep -E "분석 완료|검증 패널:|진단 완료|제안 생성" || true
}

# 대시보드는 가장 최근 분석 1건을 보여준다. 종류별 시연 중에는 정기 분석이 결과를 덮어쓰지
# 않도록 AI 서비스 컨테이너를 멈추고, 가짜 로그로 일회성 분석을 돌린다.
cmd_anomaly() {
  local kind="${1:-}"
  if [[ -z "$kind" ]]; then
    echo "종류: traffic-spike | saturation | latency | api-failure | scheduler-failure | collection-drop" >&2
    exit 1
  fi
  docker stop subway_ai_model >/dev/null
  echo "$(date '+%H:%M:%S') ${kind} 시연 — 탐지·검증·진단 실행 중 (LLM 포함 30초~1분)"
  scripts/run_anomaly_demo.sh "$kind"
  echo "$(date '+%H:%M:%S') 대시보드를 새로고침하세요. 끝나면 scripts/demo.sh restore"
}

cmd_restore() {
  scripts/run_anomaly_demo.sh restore
  docker start subway_ai_model >/dev/null
  echo "정기 분석을 다시 시작했습니다."
}

cmd_status() {
  echo "== 백엔드"
  docker ps --format '{{.Names}}  {{.Status}}' | grep -E 'backend' || true
  echo "== 최근 분석"
  docker logs subway_ai_model --since 10m 2>&1 | grep -E '분석 완료|검증 패널:|진단 완료|제안 생성' | tail -6 | cut -c12-19,40-160
  echo "== 최근 조치"
  curl -fsS -XPOST "$ES_URL/$ACTION_INDEX/_search" -H 'Content-Type: application/json' \
    -d '{"size":4,"sort":[{"created_at":"desc"}]}' 2>/dev/null \
    | python3 -c '
import json, sys
for h in json.load(sys.stdin)["hits"]["hits"]:
    s = h["_source"]; p = s.get("params", {})
    print(h["_id"], s["created_at"][:19], s["kind"], s["status"], p.get("from_replicas"), "->", p.get("to_replicas"))
' || echo "(조치 없음)"
}

# 관람객마다 한 바퀴를 돌고 처음 상태로 되돌린다. 열린 조치를 만료해 두면 쿨다운에도
# 걸리지 않으므로(만료·거부된 조치는 쿨다운 계산에서 빠진다) 바로 다음 급증을 넣을 수 있다.
cmd_reset() {
  stop_pid "$SPIKE_PID"
  reset_actions
  docker compose "${DEMO_FILES[@]}" up -d --no-recreate --scale backend=1 backend >/dev/null 2>&1
  echo "초기화 완료: backend $(docker ps --format '{{.Names}}' | grep -c 'backend')대"
}

cmd_normal() {
  stop_pid "$SPIKE_PID"
  stop_pid "$SIM_PID"
  stop_pid "$WORKER_PID"
  pkill -f traffic_simulator.sh 2>/dev/null || true
  docker compose "${BASE_FILES[@]}" up -d --scale backend=1
  reset_actions
  echo "평소 모드로 복귀했습니다 (5분 주기, backend 1대)."
}

case "${1:-}" in
  up) cmd_up ;;
  spike) cmd_spike "${2:-8}" ;;
  anomaly) cmd_anomaly "${2:-}" ;;
  restore) cmd_restore ;;
  analyze) analyze_now ;;
  status) cmd_status ;;
  reset) cmd_reset ;;
  normal) cmd_normal ;;
  *) sed -n '4,17p' "$0"; exit 1 ;;
esac
