#!/usr/bin/env bash
set -euo pipefail

ES_URL=${ES_URL:-http://localhost:9200}
REPO=${REPO:-subway_snapshots}
KEEP=${KEEP:-30}
INDEXES=${INDEXES:-${INDEX_PATTERN:-subway-logs-*},${ANOMALY_INDEX:-subway-anomaly-results}}

snapshot_id="subway-$(date +%Y%m%d-%H%M%S)"

curl -s -X PUT "$ES_URL/_snapshot/$REPO/$snapshot_id?wait_for_completion=true" \
  -H 'Content-Type: application/json' \
  -d "{\"indices\":\"$INDEXES\",\"ignore_unavailable\":true,\"include_global_state\":false}" \
  >/dev/null

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] snapshot created: $snapshot_id indices=$INDEXES"

snapshots=()
while IFS= read -r line; do
  snapshots+=("$line")
done < <(
  curl -s "$ES_URL/_cat/snapshots/$REPO?h=id,start_epoch" \
    | sort -k2n
)

snapshot_count=${#snapshots[@]}
if [[ $snapshot_count -le $KEEP ]]; then
  exit 0
fi

to_delete=$((snapshot_count - KEEP))
for ((i=0; i<to_delete; i++)); do
  snap_id=$(awk '{print $1}' <<< "${snapshots[$i]}")
  curl -s -X DELETE "$ES_URL/_snapshot/$REPO/$snap_id" >/dev/null
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] snapshot deleted: $snap_id"
done
