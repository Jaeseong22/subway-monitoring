"""graph.detection 통계 기반 이상탐지 단위 테스트.

ES/LLM 의존성 없이 순수 파이썬으로 실행: `python3 tests/test_detection.py`
근거 있는 탐지(z-score / baseline 배수 / 절대 가드레일)가 실제로 동작함을 검증한다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import detection  # noqa: E402


def build_metrics(**overrides):
    base = {
        "api": {"total": 0, "error": 0, "error_rate": 0.0, "avg_elapsed_ms": 40,
                "max_elapsed_ms": 50, "endpoints": [], "error_codes": [], "http_statuses": []},
        "traffic": {"total": 5, "error": 0, "error_rate": 0.0, "avg_elapsed_ms": 40,
                    "p95_elapsed_ms": 0, "request_count": 100, "peak_requests_per_second": 2.0,
                    "peak_cpu_percent": 20, "peak_memory_percent": 40, "peak_queue_depth": 3,
                    "instance_count": 1, "points": []},
        "scheduler": {"total": 10, "error": 0, "error_rate": 0.0, "avg_duration_ms": 300,
                      "error_messages": []},
        "collection": {"fetched_total": 2900, "line1_saved": 580, "duration_ms": 300},
    }
    for key, val in overrides.items():
        base[key] = {**base[key], **val} if isinstance(val, dict) else val
    return base


def baseline_with(**fields):
    stats = {}
    count = 0
    for name, (mean, std, n) in fields.items():
        stats[name] = {"mean": mean, "std": std, "count": n}
        count = max(count, n)
    stats["sample_count"] = count
    return stats


class DetectionTest(unittest.TestCase):

    def test_normal_no_baseline_is_normal(self):
        result = detection.evaluate(build_metrics(), {}, off_hours=False)
        self.assertEqual(result["overall_status"], "정상")
        self.assertEqual(result["today_anomaly_count"], 0)

    def test_result_schema_keys(self):
        result = detection.evaluate(build_metrics(), {}, off_hours=False)
        for key in ("overall_status", "today_anomaly_count", "latest_anomaly", "insights",
                    "anomalies", "selected_anomaly_detail", "metric_trend"):
            self.assertIn(key, result)
        self.assertIn("evidence", result["selected_anomaly_detail"])
        self.assertIn("points", result["metric_trend"])

    def test_api_failure_absolute_threshold(self):
        metrics = build_metrics(api={"total": 10, "error": 3, "error_rate": 0.30,
                                      "http_statuses": ["504"], "error_codes": ["UPSTREAM_TIMEOUT"]})
        result = detection.evaluate(metrics, {}, off_hours=False)
        self.assertEqual(result["overall_status"], "위험")
        self.assertGreaterEqual(result["today_anomaly_count"], 1)
        self.assertIn("API", result["latest_anomaly"]["title"])

    def test_api_warning_between_thresholds(self):
        metrics = build_metrics(api={"total": 100, "error": 8, "error_rate": 0.08})
        result = detection.evaluate(metrics, {}, off_hours=False)
        self.assertEqual(result["overall_status"], "주의")

    def test_latency_spike_uses_baseline(self):
        # 현재 avg 300ms vs 기준선 45±15ms → 6.7배, z≈17 → 위험
        metrics = build_metrics(traffic={"avg_elapsed_ms": 300, "peak_requests_per_second": 2.0,
                                          "peak_cpu_percent": 20, "request_count": 100})
        baseline = baseline_with(avg_elapsed_ms=(45.0, 15.0, 40))
        result = detection.evaluate(metrics, baseline, off_hours=False)
        self.assertEqual(result["overall_status"], "위험")
        titles = [a["title"] for a in result["anomalies"]]
        self.assertTrue(any("응답시간" in t for t in titles), titles)

    def test_latency_not_flagged_without_baseline(self):
        # baseline 없으면 latency는 절대판단하지 않는다(근거 부족).
        metrics = build_metrics(traffic={"avg_elapsed_ms": 300, "peak_cpu_percent": 20,
                                          "peak_requests_per_second": 2.0, "request_count": 100})
        result = detection.evaluate(metrics, {}, off_hours=False)
        self.assertEqual(result["overall_status"], "정상")

    def test_traffic_spike_uses_baseline(self):
        metrics = build_metrics(traffic={"peak_requests_per_second": 60.0, "request_count": 500,
                                          "peak_cpu_percent": 30, "avg_elapsed_ms": 40})
        baseline = baseline_with(requests_per_second=(3.0, 1.0, 40))
        result = detection.evaluate(metrics, baseline, off_hours=False)
        self.assertEqual(result["overall_status"], "위험")
        titles = [a["title"] for a in result["anomalies"]]
        self.assertTrue(any("트래픽" in t for t in titles), titles)

    def test_traffic_absolute_guardrail(self):
        # baseline 없어도 절대 요청량 임계치(1000) 초과 시 위험
        metrics = build_metrics(traffic={"request_count": 1500, "peak_requests_per_second": 50,
                                          "peak_cpu_percent": 20, "avg_elapsed_ms": 40})
        result = detection.evaluate(metrics, {}, off_hours=False)
        self.assertEqual(result["overall_status"], "위험")

    def test_saturation_absolute(self):
        metrics = build_metrics(traffic={"peak_cpu_percent": 95, "peak_memory_percent": 70,
                                          "peak_requests_per_second": 2.0, "request_count": 100})
        result = detection.evaluate(metrics, {}, off_hours=False)
        self.assertEqual(result["overall_status"], "위험")
        titles = [a["title"] for a in result["anomalies"]]
        self.assertTrue(any("포화" in t for t in titles), titles)

    def test_scheduler_failure(self):
        metrics = build_metrics(scheduler={"total": 5, "error": 2,
                                           "error_messages": ["timeout"]})
        result = detection.evaluate(metrics, {}, off_hours=False)
        self.assertEqual(result["overall_status"], "위험")

    def test_collection_drop_uses_baseline(self):
        metrics = build_metrics(collection={"fetched_total": 800})
        baseline = baseline_with(fetched_total=(2900.0, 200.0, 30))
        result = detection.evaluate(metrics, baseline, off_hours=False)
        titles = [a["title"] for a in result["anomalies"]]
        self.assertTrue(any("수집량" in t for t in titles), titles)

    def test_off_hours_ignores_api_and_scheduler(self):
        metrics = build_metrics(api={"total": 10, "error": 5, "error_rate": 0.5},
                                scheduler={"total": 3, "error": 2, "error_messages": ["x"]})
        result = detection.evaluate(metrics, {}, off_hours=True)
        self.assertEqual(result["overall_status"], "정상")
        self.assertEqual(result["today_anomaly_count"], 0)

    def test_off_hours_still_flags_saturation(self):
        metrics = build_metrics(traffic={"peak_cpu_percent": 95, "peak_requests_per_second": 2.0,
                                         "request_count": 100})
        result = detection.evaluate(metrics, {}, off_hours=True)
        self.assertEqual(result["overall_status"], "위험")

    def test_compute_baseline_stats(self):
        events = [
            {"event_type": "TRAFFIC", "event_name": "golden_signals_summary",
             "requests_per_second": "3.0", "avg_elapsed_ms": "40", "cpu_percent": "20"},
            {"event_type": "TRAFFIC", "event_name": "golden_signals_summary",
             "requests_per_second": "5.0", "avg_elapsed_ms": "60", "cpu_percent": "30"},
            {"event_type": "METRIC_COLLECTION", "fetched_total": "2900", "line1_saved": "580"},
            {"event_type": "METRIC_COLLECTION", "fetched_total": "3100", "line1_saved": "600"},
        ]
        stats = detection.compute_baseline_stats(events)
        self.assertEqual(stats["requests_per_second"]["count"], 2)
        self.assertAlmostEqual(stats["requests_per_second"]["mean"], 4.0, places=6)
        self.assertEqual(stats["fetched_total"]["count"], 2)
        self.assertAlmostEqual(stats["fetched_total"]["mean"], 3000.0, places=6)
        self.assertGreaterEqual(stats["sample_count"], 2)

    def test_zscore_and_mean_std(self):
        mean, std, n = detection.mean_std([10, 12, 14])
        self.assertEqual(n, 3)
        self.assertAlmostEqual(mean, 12.0, places=6)
        self.assertAlmostEqual(detection.zscore(20, 12, 2), 4.0, places=6)
        self.assertEqual(detection.zscore(20, 12, 0), 0.0)  # std=0 → 0


if __name__ == "__main__":
    unittest.main(verbosity=2)
