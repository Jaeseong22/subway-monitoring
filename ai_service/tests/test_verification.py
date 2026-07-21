"""검증 패널(멀티 에이전트 교차검증) 단위 테스트.

LLM 없이 실행: `python3 tests/test_verification.py`
mock lens caller로 다수결/강등 로직을 검증한다.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import verification  # noqa: E402


ANOMALY = {
    "overall_status": "위험",
    "today_anomaly_count": 1,
    "detected_keys": ["traffic"],
    "latest_anomaly": {"title": "접속 트래픽 급증", "severity": "critical"},
    "selected_anomaly_detail": {"evidence": ["최대 60 req/s = 기준선 대비 3배"]},
    "anomalies": [{"severity": "critical", "title": "접속 트래픽 급증"}],
}
METRICS = {"api": {}, "traffic": {"instance_count": 1, "peak_cpu_percent": 40}}
BASELINE = {"sample_count": 40}


class ScriptedLens:
    """렌즈 순서대로 정해진 판정을 돌려주는 mock. 각 호출이 한 렌즈."""

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = 0

    def __call__(self, system, user):
        v = self.verdicts[self.calls] if self.calls < len(self.verdicts) else "uncertain"
        self.calls += 1
        return {"verdict": v, "reason": f"{v} 근거"}


class PanelTest(unittest.TestCase):

    def test_all_real_no_downgrade(self):
        panel = verification.run(ANOMALY, METRICS, BASELINE,
                                 ScriptedLens(["real", "real", "real"]))
        self.assertEqual(panel["false_positive_votes"], 0)
        self.assertFalse(panel["downgrade"])
        self.assertEqual(len(panel["votes"]), 3)

    def test_majority_false_positive_downgrades(self):
        panel = verification.run(ANOMALY, METRICS, BASELINE,
                                 ScriptedLens(["false_positive", "false_positive", "real"]))
        self.assertEqual(panel["false_positive_votes"], 2)
        self.assertTrue(panel["downgrade"])

    def test_one_false_positive_not_enough(self):
        panel = verification.run(ANOMALY, METRICS, BASELINE,
                                 ScriptedLens(["false_positive", "real", "uncertain"]))
        self.assertEqual(panel["false_positive_votes"], 1)
        self.assertFalse(panel["downgrade"])

    def test_uncertain_does_not_downgrade(self):
        panel = verification.run(ANOMALY, METRICS, BASELINE,
                                 ScriptedLens(["uncertain", "uncertain", "uncertain"]))
        self.assertFalse(panel["downgrade"])

    def test_invalid_verdict_coerced_to_uncertain(self):
        panel = verification.run(ANOMALY, METRICS, BASELINE,
                                 ScriptedLens(["yolo", "false_positive", "false_positive"]))
        # 첫 렌즈는 uncertain으로 강등되지만 나머지 둘이 fp라 과반
        self.assertEqual(panel["votes"][0]["verdict"], "uncertain")
        self.assertTrue(panel["downgrade"])

    def test_lens_failure_becomes_uncertain(self):
        def boom(system, user):
            raise RuntimeError("timeout")
        panel = verification.run(ANOMALY, METRICS, BASELINE, boom)
        self.assertEqual([v["verdict"] for v in panel["votes"]],
                         ["uncertain", "uncertain", "uncertain"])
        self.assertFalse(panel["downgrade"])

    def test_three_distinct_lenses_run(self):
        seen = []

        def record(system, user):
            seen.append(system)
            return {"verdict": "real", "reason": ""}
        verification.run(ANOMALY, METRICS, BASELINE, record)
        self.assertEqual(len(seen), 3)
        self.assertEqual(len(set(seen)), 3)  # 세 렌즈의 시스템 프롬프트가 서로 다름


class DowngradeTest(unittest.TestCase):

    def test_no_downgrade_returns_unchanged(self):
        panel = {"downgrade": False}
        self.assertEqual(verification.apply_downgrade(ANOMALY, panel), ANOMALY)

    def test_critical_downgrades_one_step(self):
        panel = {"downgrade": True, "false_positive_votes": 2, "summary": "2/3 오탐"}
        out = verification.apply_downgrade(ANOMALY, panel)
        self.assertEqual(out["overall_status"], "주의")  # 위험 → 주의 (정상 아님)
        self.assertTrue(out["panel_downgraded"])
        self.assertGreater(out["today_anomaly_count"], 0)  # 주의라 0 아님

    def test_warning_downgrades_to_normal_and_zeroes_count(self):
        warn = {**ANOMALY, "overall_status": "주의",
                "latest_anomaly": {"severity": "warning", "title": "x"}}
        panel = {"downgrade": True, "false_positive_votes": 3, "summary": "3/3 오탐"}
        out = verification.apply_downgrade(warn, panel)
        self.assertEqual(out["overall_status"], "정상")
        self.assertEqual(out["today_anomaly_count"], 0)

    def test_downgrade_does_not_mutate_original(self):
        import json
        panel = {"downgrade": True, "false_positive_votes": 2, "summary": "x"}
        before = json.dumps(ANOMALY, ensure_ascii=False, sort_keys=True)
        verification.apply_downgrade(ANOMALY, panel)
        self.assertEqual(json.dumps(ANOMALY, ensure_ascii=False, sort_keys=True), before)

    def test_downgrade_records_evidence(self):
        panel = {"downgrade": True, "false_positive_votes": 2, "summary": "2/3 오탐"}
        out = verification.apply_downgrade(ANOMALY, panel)
        joined = " ".join(out["selected_anomaly_detail"]["evidence"])
        self.assertIn("강등", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
