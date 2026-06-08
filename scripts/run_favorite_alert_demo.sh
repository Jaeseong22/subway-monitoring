#!/usr/bin/env bash
set -euo pipefail

ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-subway_mysql}"
MYSQL_USER="${MYSQL_USER:-subway}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-subway123}"
MYSQL_DATABASE="${MYSQL_DATABASE:-subway_monitoring}"
USER_EMAIL="${USER_EMAIL:-ljs870346@gmail.com}"
DEMO_TAG="favorite-alert-demo"
STATE_FILE="${STATE_FILE:-/tmp/subway_favorite_alert_demo_state}"
DEMO_REFRESH_SECONDS="${DEMO_REFRESH_SECONDS:-300}"
ACTION="${1:-}"

usage() {
  cat <<'EOF'
Usage: scripts/run_favorite_alert_demo.sh <create|watch|cleanup>

  create   Create favorite-station alert validation data for the current day/hour.
  watch    Keep refreshing validation data for the current day/hour.
  cleanup  Delete demo USER_STATION_VIEW logs and remove the demo favorite.

Environment overrides:
  USER_EMAIL=...      User account to seed data for. Default: ljs870346@gmail.com
  STATION_ID=...      Station to use. If omitted, an arrival within 15 minutes is selected.
  STATION_NAME=...    Station display name. Usually inferred automatically.
  STATE_FILE=...      Cleanup state file. Default: /tmp/subway_favorite_alert_demo_state
  DEMO_REFRESH_SECONDS=300  Refresh interval for watch mode.
EOF
}

mysql_query() {
  docker exec "$MYSQL_CONTAINER" mysql \
    -u"$MYSQL_USER" \
    -p"$MYSQL_PASSWORD" \
    "$MYSQL_DATABASE" \
    --default-character-set=utf8mb4 \
    --batch \
    --skip-column-names \
    -e "$1"
}

require_services() {
  curl -fsS "$ES_URL" >/dev/null
  docker exec "$MYSQL_CONTAINER" mysqladmin ping \
    -u"$MYSQL_USER" \
    -p"$MYSQL_PASSWORD" \
    --default-character-set=utf8mb4 \
    --silent >/dev/null
}

sql_escape() {
  printf "%s" "$1" | sed "s/'/''/g"
}

resolve_user_id() {
  local email
  email="$(sql_escape "$USER_EMAIL")"
  mysql_query "SELECT id FROM app_user WHERE email = '$email' LIMIT 1;"
}

resolve_token() {
  local email
  email="$(sql_escape "$USER_EMAIL")"
  mysql_query "SELECT s.token
FROM auth_session s
JOIN app_user u ON u.id = s.user_id
WHERE u.email = '$email' AND s.expires_at > NOW()
ORDER BY s.expires_at DESC
LIMIT 1;"
}

resolve_station() {
  if [[ -n "${STATION_ID:-}" ]]; then
    local station_id station_name
    station_id="$STATION_ID"
    station_name="${STATION_NAME:-}"
    if [[ -z "$station_name" ]]; then
      station_name="$(mysql_query "SELECT station_name FROM arrival_info WHERE station_id = '$(sql_escape "$station_id")' ORDER BY updated_at DESC LIMIT 1;")"
    fi
    if [[ -z "$station_name" ]]; then
      station_name="$station_id"
    fi
    printf "%s\t%s\n" "$station_id" "$station_name"
    return
  fi

  mysql_query "SELECT station_id, station_name
FROM arrival_info
WHERE expected_arrival_seconds BETWEEN 0 AND 900
  AND station_id IS NOT NULL
  AND station_name IS NOT NULL
  AND station_name NOT LIKE '%?%'
ORDER BY expected_arrival_seconds ASC
LIMIT 1;"
}

upsert_favorite() {
  local user_id="$1"
  local station_id="$2"
  local station_name="$3"
  mysql_query "INSERT INTO user_station_favorite (user_id, station_id, station_name, created_at)
VALUES ($user_id, '$(sql_escape "$station_id")', '$(sql_escape "$station_name")', NOW())
ON DUPLICATE KEY UPDATE station_name = VALUES(station_name);" >/dev/null
}

delete_favorite() {
  local user_id="$1"
  local station_id="$2"
  mysql_query "DELETE FROM user_station_favorite
WHERE user_id = $user_id AND station_id = '$(sql_escape "$station_id")';" >/dev/null
}

insert_view_log() {
  local index_name="$1"
  local user_id="$2"
  local station_id="$3"
  local station_name="$4"
  local day_of_week="$5"
  local hour_of_day="$6"
  local timestamp
  timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

  curl -fsS -X POST "$ES_URL/$index_name/_doc" \
    -H 'Content-Type: application/json' \
    -d "{\"@timestamp\":\"$timestamp\",\"event_type\":\"USER_STATION_VIEW\",\"user_id\":\"$user_id\",\"station_id\":\"$station_id\",\"station_name\":\"$station_name\",\"day_of_week\":\"$day_of_week\",\"hour_of_day\":\"$hour_of_day\",\"is_favorite\":\"true\",\"duration_ms\":\"42\",\"result_count\":\"3\",\"service_name\":\"subway-demo\",\"demo_tag\":\"$DEMO_TAG\"}" \
    >/dev/null
}

delete_demo_logs() {
  curl -fsS -X POST "$ES_URL/subway-logs-*/_delete_by_query?conflicts=proceed&refresh=true" \
    -H 'Content-Type: application/json' \
    -d "{\"query\":{\"term\":{\"demo_tag.keyword\":\"$DEMO_TAG\"}}}" \
    >/dev/null
}

write_state() {
  local station_id="$1"
  {
    printf "USER_EMAIL=%s\n" "$USER_EMAIL"
    printf "STATION_ID=%s\n" "$station_id"
  } > "$STATE_FILE"
}

read_state_station_id() {
  if [[ -z "${STATION_ID:-}" && -f "$STATE_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$STATE_FILE"
  fi
  printf "%s" "${STATION_ID:-}"
}

previous_state_station_id() {
  if [[ -f "$STATE_FILE" ]]; then
    grep '^STATION_ID=' "$STATE_FILE" | tail -n 1 | cut -d= -f2-
  fi
}

print_api_checks() {
  local token="$1"
  if [[ -z "$token" ]]; then
    cat <<EOF

No active auth_session token was found for $USER_EMAIL.
The validation data was created, but API checks need a fresh login in the browser.
EOF
    return
  fi

  echo
  echo "GET /api/v1/users/me/station-patterns?days=30"
  curl -fsS "$BACKEND_URL/api/v1/users/me/station-patterns?days=30" \
    -H "Authorization: Bearer $token"

  echo
  echo
  echo "GET /api/v1/users/me/arrival-alerts"
  curl -fsS "$BACKEND_URL/api/v1/users/me/arrival-alerts" \
    -H "Authorization: Bearer $token"
  echo
}

create_demo() {
  require_services

  local user_id station_row station_id station_name day_of_week hour_raw hour_of_day index_name token
  user_id="$(resolve_user_id)"
  if [[ -z "$user_id" ]]; then
    echo "No app_user found for USER_EMAIL=$USER_EMAIL. Log in once first, then rerun this script." >&2
    exit 1
  fi

  station_row="$(resolve_station)"
  if [[ -z "$station_row" ]]; then
    echo "No station currently has an arrival within 15 minutes. Wait for arrival data or pass STATION_ID/STATION_NAME." >&2
    exit 1
  fi

  station_id="${station_row%%$'\t'*}"
  station_name="${station_row#*$'\t'}"
  day_of_week="$(TZ=Asia/Seoul date '+%A' | tr '[:lower:]' '[:upper:]')"
  hour_raw="$(TZ=Asia/Seoul date '+%H')"
  hour_of_day="$((10#$hour_raw))"
  index_name="subway-logs-$(TZ=Asia/Seoul date '+%Y.%m.%d')"

  local previous_station_id
  previous_station_id="$(previous_state_station_id)"
  if [[ -n "$previous_station_id" && "$previous_station_id" != "$station_id" ]]; then
    delete_favorite "$user_id" "$previous_station_id"
  fi

  delete_demo_logs
  upsert_favorite "$user_id" "$station_id" "$station_name"
  for _ in 1 2 3; do
    insert_view_log "$index_name" "$user_id" "$station_id" "$station_name" "$day_of_week" "$hour_of_day"
  done
  write_state "$station_id"
  curl -fsS -X POST "$ES_URL/$index_name/_refresh" >/dev/null

  echo "Favorite alert validation data created."
  echo "user_id=$user_id"
  echo "station_id=$station_id"
  echo "station_name=$station_name"
  echo "day_of_week=$day_of_week"
  echo "hour_of_day=$hour_of_day"
  echo "index=$index_name"

  token="$(resolve_token)"
  print_api_checks "$token"
}

cleanup_demo() {
  require_services

  local user_id station_row station_id
  user_id="$(resolve_user_id)"
  station_id="$(read_state_station_id)"
  if [[ -n "$station_id" ]]; then
    station_row="$station_id"$'\t'"${STATION_NAME:-$station_id}"
  else
    station_row="$(resolve_station || true)"
  fi
  if [[ -n "$user_id" && -n "$station_row" ]]; then
    station_id="${station_row%%$'\t'*}"
    delete_favorite "$user_id" "$station_id"
  fi
  delete_demo_logs
  rm -f "$STATE_FILE"
  echo "Favorite alert demo data cleaned up."
}

watch_demo() {
  echo "Refreshing favorite alert validation data every ${DEMO_REFRESH_SECONDS}s."
  echo "Press Ctrl+C to stop. Run 'scripts/run_favorite_alert_demo.sh cleanup' after the demo."
  while true; do
    create_demo
    sleep "$DEMO_REFRESH_SECONDS"
  done
}

case "$ACTION" in
  create)
    create_demo
    ;;
  watch)
    watch_demo
    ;;
  cleanup)
    cleanup_demo
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
