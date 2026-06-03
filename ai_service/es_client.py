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

    def fetch_baseline_events(self, day_of_week: str, hour_of_day: str) -> list[dict[str, Any]]:
        resp = self.client.search(
            index=self.log_index_pattern,
            size=2000,
            query={
                "bool": {
                    "filter": [
                        {"term": {"event_type": "METRIC_COLLECTION"}},
                        {"term": {"day_of_week": day_of_week}},
                        {"term": {"hour_of_day": hour_of_day}},
                        {"range": {"@timestamp": {"gte": "now-28d/d"}}},
                    ]
                }
            },
            _source=[
                "@timestamp",
                "up_count",
                "down_count",
                "fetched_total",
                "line1_saved",
                "duration_ms",
                "time_category",
                "day_of_week",
                "hour_of_day",
            ],
        )
        return [hit.get("_source", {}) for hit in resp.get("hits", {}).get("hits", [])]

    def save_anomaly_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.client.index(index=self.anomaly_index, document=payload)
