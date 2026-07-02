import os
from dataclasses import dataclass
from datetime import datetime, timedelta
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
        self.client = Elasticsearch(self.url, request_timeout=30)

    def _window(self, lookback_minutes: int) -> AnalysisWindow:
        end = datetime.utcnow()
        start = end - timedelta(minutes=lookback_minutes)
        return AnalysisWindow(start=start, end=end)

    def fetch_recent_events(self, lookback_minutes: int) -> tuple[AnalysisWindow, list[dict[str, Any]]]:
        window = self._window(lookback_minutes)
        resp = self.client.search(
            index=self.log_index_pattern,
            size=2000,
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

    def save_anomaly_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.client.index(index=self.anomaly_index, document=payload)
