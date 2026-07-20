"""graph.detection 통계 기반 이상탐지 단위 테스트.

ES/LLM 의존성 없이 순수 파이썬으로 실행: `python3 tests/test_detection.py`
근거 있는 탐지(z-score / baseline 배수 / 절대 가드레일)가 실제로 동작함을 검증한다.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import detection, llm_merge  # noqa: E402


def build_metrics(**overrides):
    base = {
        "api": {"total": 0, "error": 0, "error_rate": 0.0, "avg_elapsed_ms": 40,
                "max_elapsed_ms": 50, "endpoints": [], "error_codes": [], "http_statuses": []},
        "traffic": {"total": 5, "error": 0, "error_rate": 0.0, "avg_elapsed_ms": 40,
                    "peak_elapsed_ms": 55, "p95_elapsed_ms": 0, "peak_p95_elapsed_ms": 0,
                    "request_count": 100, "requests_per_second": 2.0,
                    "peak_requests_per_second": 2.0,
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
    """fields: name=(mean, std, n) 또는 name=(mean, std, n, p99)"""
    stats = {}
    count = 0
    for name, spec in fields.items():
        mean, std, n = spec[0], spec[1], spec[2]
        p99 = spec[3] if len(spec) > 3 else mean + 3 * std
        stats[name] = {"mean": mean, "std": std, "count": n,
                       "p95": mean + 2 * std, "p99": p99}
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
        metrics = build_metrics(traffic={"requests_per_second": 60.0,
                                          "peak_requests_per_second": 80.0, "request_count": 500,
                                          "peak_cpu_percent": 30, "avg_elapsed_ms": 40})
        baseline = baseline_with(requests_per_second=(3.0, 1.0, 40))
        result = detection.evaluate(metrics, baseline, off_hours=False)
        self.assertEqual(result["overall_status"], "위험")
        titles = [a["title"] for a in result["anomalies"]]
        self.assertTrue(any("트래픽" in t for t in titles), titles)

    def test_traffic_absolute_guardrail_uses_rps(self):
        # baseline이 없으면 rps 절대 임계치(기본 50 req/s)로 판단한다.
        metrics = build_metrics(traffic={"request_count": 1500, "requests_per_second": 40,
                                          "peak_requests_per_second": 50,
                                          "peak_cpu_percent": 20, "avg_elapsed_ms": 40})
        result = detection.evaluate(metrics, {}, off_hours=False)
        self.assertEqual(result["overall_status"], "위험")

    def test_high_request_count_alone_is_not_anomaly(self):
        """회귀: 총 요청수 1000건은 창 길이에 의존하므로 그것만으로 위험이 되면 안 된다.

        기존 로직은 request_count>=1000을 무조건 critical로 봤는데, 30분 창 기준
        0.56 req/s에 불과해 실서비스에서 상시 발화하는 상수 알람이었다.
        """
        metrics = build_metrics(traffic={"request_count": 5000, "requests_per_second": 2.8,
                                          "peak_requests_per_second": 4.0,
                                          "peak_cpu_percent": 20, "avg_elapsed_ms": 40})
        result = detection.evaluate(metrics, {}, off_hours=False)
        self.assertEqual(result["overall_status"], "정상")

    def test_peak_is_not_compared_against_baseline_mean(self):
        """회귀(핵심): 창 피크를 기준선 평균과 비교하면 안 된다.

        E[max of N] > mean 이므로, 정상 상태에서도 피크는 평균의 몇 배가 된다.
        창 평균이 기준선 평균과 같다면 피크가 3배여도 이상이 아니어야 한다.
        """
        metrics = build_metrics(traffic={"requests_per_second": 3.0,      # 기준선 평균과 동일
                                          "peak_requests_per_second": 9.0,  # 평균의 3배
                                          "request_count": 90, "avg_elapsed_ms": 40,
                                          "peak_cpu_percent": 20})
        baseline = baseline_with(requests_per_second=(3.0, 1.0, 40, 12.0))
        result = detection.evaluate(metrics, baseline, off_hours=False)
        self.assertEqual(result["overall_status"], "정상")

    def test_z_gate_blocks_high_ratio_with_low_z(self):
        """배수 조건을 넘어도 분산이 커서 z가 낮으면 이상으로 보지 않는다."""
        metrics = build_metrics(traffic={"requests_per_second": 5.0,
                                          "peak_requests_per_second": 6.0,
                                          "request_count": 150, "avg_elapsed_ms": 40,
                                          "peak_cpu_percent": 20})
        # ratio = 5/2 = 2.5 (>=2.0 통과) 이지만 z = (5-2)/5 = 0.6 (<2.0) → 미판정
        baseline = baseline_with(requests_per_second=(2.0, 5.0, 40, 20.0))
        result = detection.evaluate(metrics, baseline, off_hours=False)
        self.assertEqual(result["overall_status"], "정상")

    def test_latency_z_gate_blocks_noisy_baseline(self):
        metrics = build_metrics(traffic={"avg_elapsed_ms": 100, "peak_elapsed_ms": 120,
                                          "requests_per_second": 2.0,
                                          "peak_requests_per_second": 2.0,
                                          "request_count": 100, "peak_cpu_percent": 20})
        # ratio = 100/50 = 2.0 이지만 std=100이라 z=0.5 → 근거 부족으로 미판정
        baseline = baseline_with(avg_elapsed_ms=(50.0, 100.0, 40, 400.0))
        result = detection.evaluate(metrics, baseline, off_hours=False)
        self.assertEqual(result["overall_status"], "정상")

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

    def test_percentile(self):
        vals = list(range(1, 101))  # 1..100
        self.assertAlmostEqual(detection.percentile(vals, 0.0), 1.0, places=6)
        self.assertAlmostEqual(detection.percentile(vals, 1.0), 100.0, places=6)
        self.assertAlmostEqual(detection.percentile(vals, 0.5), 50.5, places=6)
        self.assertEqual(detection.percentile([], 0.95), 0.0)
        self.assertEqual(detection.percentile([7.0], 0.95), 7.0)

    def test_baseline_stats_include_quantiles(self):
        events = [{"event_type": "TRAFFIC", "event_name": "golden_signals_summary",
                   "requests_per_second": str(float(v))} for v in range(1, 21)]
        stats = detection.compute_baseline_stats(events)
        self.assertEqual(stats["requests_per_second"]["count"], 20)
        self.assertGreater(stats["requests_per_second"]["p99"],
                           stats["requests_per_second"]["mean"])


class DebounceTest(unittest.TestCase):
    """플래핑 방지: 연속 N회 감지된 신호만 확정으로 승격한다."""

    def spiking_metrics(self):
        return build_metrics(traffic={"peak_cpu_percent": 95, "peak_memory_percent": 70,
                                      "requests_per_second": 2.0,
                                      "peak_requests_per_second": 2.0, "request_count": 100})

    def test_detected_keys_are_reported(self):
        result = detection.evaluate(self.spiking_metrics(), {}, off_hours=False)
        self.assertIn("saturation", result["detected_keys"])

    def test_single_spike_is_pending_not_confirmed(self):
        # 직전 실행에서 감지되지 않았으면 확정하지 않는다(단발성 스파이크 억제).
        result = detection.evaluate(self.spiking_metrics(), {}, off_hours=False,
                                    recent_keys=[[]])
        self.assertEqual(result["overall_status"], "정상")
        self.assertEqual(result["today_anomaly_count"], 0)
        self.assertEqual([p["key"] for p in result["pending_signals"]], ["saturation"])

    def test_consecutive_detection_is_confirmed(self):
        result = detection.evaluate(self.spiking_metrics(), {}, off_hours=False,
                                    recent_keys=[["saturation"]])
        self.assertEqual(result["overall_status"], "위험")
        self.assertEqual(result["pending_signals"], [])

    def test_cold_start_does_not_suppress(self):
        # 이력이 아직 없으면(첫 실행) 억제하지 않는다.
        result = detection.evaluate(self.spiking_metrics(), {}, off_hours=False,
                                    recent_keys=[])
        self.assertEqual(result["overall_status"], "위험")


class LlmMergeTest(unittest.TestCase):
    """LLM은 서술 텍스트만 바꿀 수 있고 판정·수치는 통계 결과가 강제된다."""

    def grounded(self):
        metrics = build_metrics(traffic={"peak_cpu_percent": 95, "requests_per_second": 2.0,
                                         "peak_requests_per_second": 2.0, "request_count": 100})
        return detection.evaluate(metrics, {}, off_hours=False)

    def test_llm_cannot_downgrade_verdict(self):
        grounded = self.grounded()
        self.assertEqual(grounded["overall_status"], "위험")
        hostile = {
            "overall_status": "정상",
            "today_anomaly_count": 0,
            "latest_anomaly": {"severity": "info", "title": "괜찮음", "summary": "문제 없습니다"},
            "anomalies": [],
            "metric_trend": {"label": "가짜", "points": [{"ts": "x", "value": 0}]},
        }
        merged = llm_merge.merge_llm_result(grounded, hostile)
        self.assertEqual(merged["overall_status"], "위험")
        self.assertEqual(merged["today_anomaly_count"], grounded["today_anomaly_count"])
        self.assertEqual(merged["latest_anomaly"]["severity"], "critical")
        self.assertEqual(merged["metric_trend"], grounded["metric_trend"])
        self.assertEqual(len(merged["anomalies"]), len(grounded["anomalies"]))
        # 서술 텍스트는 채택된다.
        self.assertEqual(merged["latest_anomaly"]["title"], "괜찮음")

    def test_llm_narrative_is_adopted(self):
        grounded = self.grounded()
        merged = llm_merge.merge_llm_result(grounded, {
            "selected_anomaly_detail": {
                "description": "CPU가 95%까지 올라 처리 지연이 예상됩니다.",
                "recommended_actions": ["인스턴스 증설", "캐시 적용"],
            },
        })
        self.assertIn("95%", merged["selected_anomaly_detail"]["description"])
        self.assertEqual(merged["selected_anomaly_detail"]["recommended_actions"],
                         ["인스턴스 증설", "캐시 적용"])

    def test_malformed_llm_output_falls_back(self):
        grounded = self.grounded()
        for junk in (None, [], "문자열", {"latest_anomaly": "not a dict"}, {"insights": [1, 2, 3]}):
            self.assertEqual(llm_merge.merge_llm_result(grounded, junk)["overall_status"], "위험")

    def test_merge_does_not_mutate_grounded(self):
        grounded = self.grounded()
        original = json.dumps(grounded, ensure_ascii=False, sort_keys=True)
        llm_merge.merge_llm_result(grounded, {"latest_anomaly": {"title": "바뀐 제목"}})
        self.assertEqual(json.dumps(grounded, ensure_ascii=False, sort_keys=True), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
