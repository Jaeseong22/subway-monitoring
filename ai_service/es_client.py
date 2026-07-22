import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from elasticsearch import Elasticsearch


@dataclass
class AnalysisWindow:
    start: datetime
    end: datetime


class ElasticsearchClient:
    def __init__(self) -> None:
        self.url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        self.log_index_pattern = os.getenv("LOG_INDEX_PATTERN", "subway-logs-*")
        self.anomaly_index = os.getenv("ANOMALY_INDEX", "subway-anomaly-results")
        self.action_index = os.getenv("REMEDIATION_INDEX", "subway-remediation-actions")
        self.client = Elasticsearch(self.url, request_timeout=30)

    def _window(self, lookback_minutes: int) -> AnalysisWindow:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=lookback_minutes)
        return AnalysisWindow(start=start, end=end)

    def fetch_recent_events(self, lookback_minutes: int) -> tuple[AnalysisWindow, list[dict[str, Any]]]:
        window = self._window(lookback_minutes)
        resp = self.client.search(
            index=self.log_index_pattern,
            size=2000,
            # 정렬을 지정하지 않으면 ES는 순서를 보장하지 않는다. size 상한에 걸릴 때
            # 임의 부분집합이 아니라 '최신 N건'이 오도록 명시한다.
            sort=[{"@timestamp": {"order": "desc"}}],
            query={
                "bool": {
                    "filter": [
                        {"range": {"@timestamp": {"gte": window.start.isoformat(), "lte": window.end.isoformat()}}}
                    ]
                }
            },
            _source=[
                "@timestamp",
                "event_type",
                "success",
                "elapsed_ms",
                "duration_ms",
                "error_msg",
                "error_code",
                "http_status",
                "endpoint",
                "event_name",
                "api_name",
                "scheduler_name",
                "request_count",
                "requests_per_second",
                "cpu_percent",
                "memory_percent",
                "instance_count",
                "instance_id",
                "instance_role",
                "queue_depth",
                "up_count",
                "down_count",
                "fetched_total",
                "line1_saved",
                "time_category",
                "day_of_week",
                "is_weekend",
                "hour_of_day",
                "congestion_station",
                "congestion_count",
                "average_count",
                "service_name",
                "message",
            ],
        )
        hits = [hit.get("_source", {}) for hit in resp.get("hits", {}).get("hits", [])]
        return window, hits

    def fetch_baseline_events(self, hour_of_day: str, is_weekend: str) -> list[dict[str, Any]]:
        """과거 28일 중 같은 시간대(hour_of_day) + 같은 평일/주말(is_weekend)의
        Golden Signals 요약(TRAFFIC/golden_signals_summary)과 수집 메트릭(METRIC_COLLECTION)을
        조회한다. 이 표본으로 신호별 평균/표준편차 기준선을 만든다.

        Logstash 동적 매핑상 문자열은 분석된 text + `.keyword` 서브필드로 색인되므로
        정확 일치 term 쿼리는 반드시 `.keyword`를 대상으로 한다.
        """
        resp = self.client.search(
            index=self.log_index_pattern,
            size=5000,
            query={
                "bool": {
                    "filter": [
                        {"term": {"hour_of_day.keyword": hour_of_day}},
                        {"term": {"is_weekend.keyword": is_weekend}},
                        {"range": {"@timestamp": {"gte": "now-28d/d"}}},
                        {
                            "bool": {
                                "should": [
                                    {"term": {"event_type.keyword": "METRIC_COLLECTION"}},
                                    {
                                        "bool": {
                                            "filter": [
                                                {"term": {"event_type.keyword": "TRAFFIC"}},
                                                {"term": {"event_name.keyword": "golden_signals_summary"}},
                                            ]
                                        }
                                    },
                                ],
                                "minimum_should_match": 1,
                            }
                        },
                    ]
                }
            },
            _source=[
                "@timestamp",
                "event_type",
                "event_name",
                "is_weekend",
                "hour_of_day",
                # Golden Signals 요약 지표 (rate/ratio/point → 창 길이 무관 비교 가능)
                "requests_per_second",
                "error_rate",
                "avg_elapsed_ms",
                "p95_elapsed_ms",
                "cpu_percent",
                "memory_percent",
                # 수집 메트릭
                "fetched_total",
                "line1_saved",
                "duration_ms",
            ],
        )
        return [hit.get("_source", {}) for hit in resp.get("hits", {}).get("hits", [])]

    def fetch_recent_detected_keys(self, size: int) -> list[list[str]]:
        """직전 분석 실행들이 감지한 신호 key 목록을 최신순으로 반환한다.

        디바운스(연속 N회 감지 시에만 확정)를 위해 별도 상태 저장소를 두지 않고
        이미 저장 중인 이상탐지 결과 인덱스를 이력으로 재사용한다.
        인덱스가 아직 없으면 빈 목록을 반환한다.
        """
        if size <= 0:
            return []
        if not self.client.indices.exists(index=self.anomaly_index):
            return []
        resp = self.client.search(
            index=self.anomaly_index,
            size=size,
            sort=[{"@timestamp": {"order": "desc"}}],
            query={"match_all": {}},
            _source=["result.detected_keys"],
        )
        history = []
        for hit in resp.get("hits", {}).get("hits", []):
            result = (hit.get("_source", {}) or {}).get("result", {}) or {}
            keys = result.get("detected_keys")
            history.append([str(k) for k in keys] if isinstance(keys, list) else [])
        return history

    def save_anomaly_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.client.index(index=self.anomaly_index, document=payload)

    def fetch_latest_analysis(self) -> dict[str, Any]:
        """가장 최근 분석 문서의 result/metrics/diagnosis를 반환한다(재계획·검증용)."""
        resp = self.client.search(
            index=self.anomaly_index,
            size=1,
            sort=[{"@timestamp": {"order": "desc"}}],
            query={"match_all": {}},
        )
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return {"result": {}, "metrics": {}, "diagnosis": None}
        source = hits[0].get("_source", {}) or {}
        return {"result": source.get("result", {}) or {},
                "metrics": source.get("metrics", {}) or {},
                "diagnosis": source.get("diagnosis")}

    # ---------------------------------------------------------------- 자동 대응
    def fetch_recent_actions(self, size: int = 20) -> list[dict[str, Any]]:
        """최근 자동 대응 조치를 최신순으로 조회한다(쿨다운·중복 제안 판정에 사용)."""
        if not self.client.indices.exists(index=self.action_index):
            return []
        resp = self.client.search(
            index=self.action_index,
            size=size,
            sort=[{"created_at": {"order": "desc"}}],
            query={"match_all": {}},
        )
        actions = []
        for hit in resp.get("hits", {}).get("hits", []):
            action = dict(hit.get("_source", {}) or {})
            action["action_id"] = hit.get("_id")
            actions.append(action)
        return actions

    def save_action(self, action: dict[str, Any]) -> str:
        """새 조치를 저장하고 생성된 문서 id를 반환한다."""
        payload = {k: v for k, v in action.items() if k != "action_id"}
        payload.setdefault("@timestamp", payload.get("created_at"))
        resp = self.client.index(index=self.action_index, document=payload, refresh=True)
        return resp.get("_id")

    def update_action(self, action_id: str, action: dict[str, Any]) -> None:
        payload = {k: v for k, v in action.items() if k != "action_id"}
        self.client.index(index=self.action_index, id=action_id, document=payload, refresh=True)
