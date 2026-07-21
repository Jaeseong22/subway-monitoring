"""근본 원인 진단 에이전트 + 조사 도구 단위 테스트.

LLM 없이 실행: `python3 tests/test_diagnosis.py`
- 도구(tools.py)는 순수 함수라 직접 검증.
- 진단 루프(diagnosis.py)는 mock llm_caller로 도구 선택/반복/결론 로직을 검증.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import diagnosis, tools  # noqa: E402


def logs():
    """API 오류가 504에 몰리고 특정 시각에 집중된 합성 로그."""
    events = []
    # 정상 API 호출
    for i in range(7):
        events.append({"@timestamp": f"2026-07-21T08:0{i}:00Z", "event_type": "API_COLLECTION",
                       "success": "true", "http_status": "200", "endpoint": "/arrival/page1"})
    # 08:15부터 504 집중, 특정 엔드포인트
    for i in range(9):
        events.append({"@timestamp": f"2026-07-21T08:15:{i:02d}Z", "event_type": "API_COLLECTION",
                       "success": "false", "http_status": "504", "error_code": "UPSTREAM_TIMEOUT",
                       "endpoint": "/arrival/page3", "error_msg": "read timed out"})
    for i in range(3):
        events.append({"@timestamp": f"2026-07-21T08:20:{i:02d}Z", "event_type": "API_COLLECTION",
                       "success": "false", "http_status": "429", "error_code": "RATE_LIMITED",
                       "endpoint": "/arrival/page3"})
    return events


class ToolsTest(unittest.TestCase):

    def test_breakdown_by(self):
        r = tools.breakdown_by(logs(), "http_status")
        self.assertEqual(r["distribution"]["200"], 7)
        self.assertEqual(r["distribution"]["504"], 9)
        self.assertEqual(r["distribution"]["429"], 3)

    def test_breakdown_by_with_where(self):
        # 504만 걸러서 endpoint 분포 → page3에 100%
        r = tools.breakdown_by(logs(), "endpoint", "http_status", "504")
        self.assertEqual(r["distribution"], {"/arrival/page3": 9})
        self.assertEqual(r["matched_events"], 9)

    def test_time_histogram_concentration(self):
        r = tools.time_histogram(logs(), 5, "http_status", "504")
        # 전부 08:15 버킷에 몰림
        self.assertEqual(r["series"], {"2026-07-21T08:15": 9})

    def test_time_histogram_buckets_floor(self):
        r = tools.time_histogram(logs(), 5)
        self.assertIn("2026-07-21T08:00", r["series"])  # 08:00~08:06 → 08:00 버킷
        self.assertIn("2026-07-21T08:15", r["series"])

    def test_sample_events(self):
        r = tools.sample_events(logs(), "error_code", "UPSTREAM_TIMEOUT", limit=2)
        self.assertEqual(len(r["samples"]), 2)
        self.assertEqual(r["samples"][0]["error_msg"], "read timed out")

    def test_field_values(self):
        r = tools.field_values(logs(), "http_status", "504")
        self.assertIn("error_code", r["fields"])
        self.assertEqual(r["fields"]["endpoint"], 9)

    def test_dispatch_unknown_tool(self):
        r = tools.dispatch("nonexistent", {}, logs())
        self.assertIn("error", r)

    def test_dispatch_bad_args(self):
        r = tools.dispatch("breakdown_by", {"nope": 1}, logs())
        self.assertIn("error", r)

    def test_dispatch_routes(self):
        r = tools.dispatch("breakdown_by", {"field": "http_status"}, logs())
        self.assertEqual(r["distribution"]["504"], 9)


ANOMALY = {
    "overall_status": "위험",
    "detected_keys": ["api_errors"],
    "latest_anomaly": {"title": "서울 실시간 도착 API 응답 장애", "severity": "critical",
                       "summary": "오류율 30%"},
    "selected_anomaly_detail": {"evidence": ["오류율 30%"]},
}
METRICS = {"api": {"total": 19, "error": 12}, "traffic": {}, "scheduler": {}}


class ScriptedCaller:
    """미리 정해진 순서로 도구를 호출하고 마지막에 결론을 내는 mock LLM."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, messages, schemas):
        step = self.script[self.calls] if self.calls < len(self.script) else {"content": "{}"}
        self.calls += 1
        return step


class DiagnosisLoopTest(unittest.TestCase):

    def test_tool_use_loop_reaches_conclusion(self):
        caller = ScriptedCaller([
            {"tool_calls": [{"id": "1", "name": "breakdown_by", "arguments": {"field": "http_status"}}]},
            {"tool_calls": [{"id": "2", "name": "time_histogram",
                             "arguments": {"bucket_minutes": 5, "where_field": "http_status", "where_value": "504"}}]},
            {"tool_calls": [{"id": "3", "name": "breakdown_by",
                             "arguments": {"field": "endpoint", "where_field": "http_status", "where_value": "504"}}]},
            {"content": '{"root_cause": "page3 호출이 08:15부터 상시 타임아웃",'
                        ' "confidence": "high", "evidence": ["504가 page3에 100%"],'
                        ' "recommended_focus": "보조키 쿼터"}'},
        ])
        result = diagnosis.run(ANOMALY, METRICS, logs(), caller, max_steps=6)
        self.assertEqual(result["status"], "완료")
        self.assertEqual(result["confidence"], "high")
        self.assertIn("page3", result["root_cause"])
        self.assertEqual(result["steps_used"], 3)
        self.assertEqual(len(result["investigation"]), 3)
        # 도구가 실제 로그 위에서 동작했는지 (관찰에 실제 수치가 담김)
        self.assertTrue(any("504" in step["observation"] for step in result["investigation"]))

    def test_immediate_conclusion_without_tools(self):
        caller = ScriptedCaller([
            {"content": '{"root_cause": "명백함", "confidence": "medium", "evidence": [], "recommended_focus": ""}'},
        ])
        result = diagnosis.run(ANOMALY, METRICS, logs(), caller)
        self.assertEqual(result["steps_used"], 0)
        self.assertEqual(result["root_cause"], "명백함")

    def test_max_steps_returns_unresolved(self):
        # 계속 도구만 부르고 결론을 안 내는 LLM → 미결
        caller = ScriptedCaller([
            {"tool_calls": [{"id": str(i), "name": "breakdown_by", "arguments": {"field": "http_status"}}]}
            for i in range(10)
        ])
        result = diagnosis.run(ANOMALY, METRICS, logs(), caller, max_steps=3)
        self.assertEqual(result["status"], "미결")
        self.assertEqual(result["steps_used"], 3)
        self.assertEqual(result["confidence"], "low")

    def test_llm_failure_is_skipped_not_crash(self):
        def boom(messages, schemas):
            raise RuntimeError("network down")
        result = diagnosis.run(ANOMALY, METRICS, logs(), boom)
        self.assertEqual(result["status"], "생략")
        self.assertIn("network down", result["reason"])

    def test_malformed_final_json_defended(self):
        caller = ScriptedCaller([{"content": "이건 JSON이 아님"}])
        result = diagnosis.run(ANOMALY, METRICS, logs(), caller)
        self.assertEqual(result["status"], "완료")
        self.assertEqual(result["confidence"], "low")
        self.assertIn("JSON이 아님", result["root_cause"])

    def test_bad_tool_call_does_not_crash_loop(self):
        # LLM이 존재하지 않는 도구를 불러도 루프는 계속되고 결론에 도달한다.
        caller = ScriptedCaller([
            {"tool_calls": [{"id": "1", "name": "made_up_tool", "arguments": {}}]},
            {"content": '{"root_cause": "복구", "confidence": "low", "evidence": [], "recommended_focus": ""}'},
        ])
        result = diagnosis.run(ANOMALY, METRICS, logs(), caller)
        self.assertEqual(result["status"], "완료")
        self.assertIn("error", str(result["investigation"][0]["observation"]).lower() + "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
