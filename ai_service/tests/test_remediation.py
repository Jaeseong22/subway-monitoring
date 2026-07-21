"""graph.remediation 자동 대응 제안·검증 단위 테스트.

ES/Docker 의존성 없이 순수 파이썬으로 실행: `python3 tests/test_remediation.py`
가드레일(상한/쿨다운/중복)과 검증·롤백 판정이 실제로 동작함을 검증한다.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import detection, remediation  # noqa: E402

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def cfg(**overrides):
    base = {
        "enabled": True, "auto_approve": False, "service": "backend",
        "max_replicas": 4, "min_replicas": 1, "cooldown_minutes": 15,
        "verify_after_minutes": 10, "expire_after_minutes": 60,
        "scale_in_after_normal_runs": 6, "cpu_warn": 60,
    }
    base.update(overrides)
    return base


def anomalous(keys=("traffic",), severity="critical"):
    return {
        "overall_status": "위험",
        "detected_keys": list(keys),
        "anomalies": [{"severity": severity, "title": "접속 트래픽 급증"}],
        "latest_anomaly": {"severity": severity, "title": "접속 트래픽 급증"},
        "selected_anomaly_detail": {"evidence": ["최대 60 req/s"]},
    }


def normal():
    return {
        "overall_status": "정상", "detected_keys": [], "anomalies": [],
        "latest_anomaly": {"severity": "info", "title": "특이 이상 없음"},
        "selected_anomaly_detail": {"evidence": []},
    }


def metrics(instances=1):
    return {"traffic": {"instance_count": instances, "peak_requests_per_second": 60.0,
                        "peak_cpu_percent": 85.0, "peak_memory_percent": 70.0}}


class ProposeTest(unittest.TestCase):

    def test_scale_out_on_confirmed_traffic(self):
        action = remediation.propose(anomalous(), metrics(1), [], now_iso=NOW_ISO, cfg=cfg())
        self.assertIsNotNone(action)
        self.assertEqual(action["kind"], remediation.SCALE_OUT)
        self.assertEqual(action["status"], remediation.PENDING)
        self.assertEqual(action["params"]["from_replicas"], 1)
        self.assertEqual(action["params"]["to_replicas"], 2)

    def test_no_proposal_when_normal(self):
        self.assertIsNone(remediation.propose(normal(), metrics(1), [], now_iso=NOW_ISO, cfg=cfg()))

    def test_no_proposal_for_non_scalable_signal(self):
        """스케줄러 실패나 외부 API 장애는 서버를 늘려도 해결되지 않는다."""
        for key in ("scheduler", "api_errors", "collection"):
            result = anomalous(keys=(key,))
            self.assertIsNone(
                remediation.propose(result, metrics(1), [], now_iso=NOW_ISO, cfg=cfg()),
                f"{key} 신호로 확장을 제안하면 안 된다")

    def test_max_replicas_guardrail(self):
        action = remediation.propose(anomalous(), metrics(4), [], now_iso=NOW_ISO, cfg=cfg())
        self.assertTrue(action["blocked"])
        self.assertEqual(action["params"]["to_replicas"], 4)
        self.assertIn("최대 인스턴스", action["reason"])

    def test_cooldown_blocks_repeat_proposal(self):
        recent = [{"status": remediation.SUCCEEDED,
                   "executed_at": (NOW - timedelta(minutes=5)).isoformat()}]
        self.assertIsNone(remediation.propose(anomalous(), metrics(1), recent,
                                              now_iso=NOW_ISO, cfg=cfg()))

    def test_cooldown_expires(self):
        recent = [{"status": remediation.SUCCEEDED,
                   "executed_at": (NOW - timedelta(minutes=30)).isoformat()}]
        self.assertIsNotNone(remediation.propose(anomalous(), metrics(1), recent,
                                                 now_iso=NOW_ISO, cfg=cfg()))

    def test_open_action_blocks_duplicate(self):
        for status in remediation.OPEN_STATUSES:
            recent = [{"status": status, "created_at": (NOW - timedelta(hours=5)).isoformat()}]
            self.assertIsNone(
                remediation.propose(anomalous(), metrics(1), recent, now_iso=NOW_ISO, cfg=cfg()),
                f"{status} 조치가 열려 있으면 중복 제안하면 안 된다")

    def test_rejected_action_does_not_block(self):
        recent = [{"status": remediation.REJECTED,
                   "created_at": (NOW - timedelta(minutes=1)).isoformat()}]
        self.assertIsNotNone(remediation.propose(anomalous(), metrics(1), recent,
                                                 now_iso=NOW_ISO, cfg=cfg()))

    def test_scale_in_after_sustained_normal(self):
        action = remediation.propose(normal(), metrics(3), [], normal_streak=6,
                                     now_iso=NOW_ISO, cfg=cfg())
        self.assertEqual(action["kind"], remediation.SCALE_IN)
        self.assertEqual(action["params"]["to_replicas"], 2)

    def test_scale_in_requires_streak(self):
        self.assertIsNone(remediation.propose(normal(), metrics(3), [], normal_streak=2,
                                              now_iso=NOW_ISO, cfg=cfg()))

    def test_scale_in_respects_min_replicas(self):
        self.assertIsNone(remediation.propose(normal(), metrics(1), [], normal_streak=99,
                                              now_iso=NOW_ISO, cfg=cfg()))

    def test_disabled_produces_nothing(self):
        self.assertIsNone(remediation.propose(anomalous(), metrics(1), [], now_iso=NOW_ISO,
                                              cfg=cfg(enabled=False)))


class InstanceCountTest(unittest.TestCase):
    """가동 API 인스턴스 수 집계 — 자동 확장 판단의 입력이므로 정확해야 한다."""

    def setUp(self):
        self.count = detection.count_api_instances

    def golden(self, instance_id, role="api", minute="2026-07-20T12:05"):
        return {"@timestamp": f"{minute}:00.000Z", "instance_id": instance_id,
                "instance_role": role, "event_name": "golden_signals_summary"}

    def test_counts_distinct_api_instances(self):
        events = [self.golden("a"), self.golden("b"), self.golden("a")]
        self.assertEqual(self.count(events), 2)

    def test_excludes_collector(self):
        """수집 전용 프로세스는 로드밸런서 뒤에 없으므로 확장 대상이 아니다."""
        events = [self.golden("api-1"), self.golden("api-2"),
                  self.golden("collector-1", role="collector")]
        self.assertEqual(self.count(events), 2)

    def test_ignores_stale_instances_from_earlier_buckets(self):
        """재시작·축소된 인스턴스가 분석 창에 남아 과다 집계되면 안 된다."""
        events = [
            self.golden("old-1", minute="2026-07-20T12:00"),
            self.golden("old-2", minute="2026-07-20T12:01"),
            self.golden("new-1", minute="2026-07-20T12:05"),
            self.golden("new-2", minute="2026-07-20T12:05"),
        ]
        self.assertEqual(self.count(events), 2)

    def test_empty_is_zero(self):
        self.assertEqual(self.count([]), 0)
        self.assertEqual(self.count([self.golden("c", role="collector")]), 0)

    def test_falls_back_to_instance_count_field(self):
        """instance_id를 남기지 않는 구버전 로그와의 호환."""
        events = [{"instance_count": "3", "event_name": "golden_signals_summary"}]
        self.assertEqual(self.count(events), 3)


class CommandTest(unittest.TestCase):

    def test_scale_command(self):
        action = {"params": {"service": "backend", "to_replicas": 3}}
        cmd = remediation.scale_command(action, ["docker-compose.yml", "docker-compose.scale.yml"])
        self.assertEqual(cmd[:2], ["docker", "compose"])
        self.assertIn("--scale", cmd)
        self.assertIn("backend=3", cmd)
        # 기존 컨테이너를 불필요하게 재생성하지 않는다.
        self.assertIn("--no-recreate", cmd)


class VerifyTest(unittest.TestCase):

    def executed(self, kind=remediation.SCALE_OUT, keys=("traffic",), minutes_ago=15):
        return {
            "status": remediation.EXECUTED,
            "kind": kind,
            "executed_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
            "trigger": {"signal_keys": list(keys)},
            "params": {"service": "backend", "from_replicas": 1, "to_replicas": 2},
        }

    def test_ready_to_verify_after_wait(self):
        self.assertTrue(remediation.is_ready_to_verify(self.executed(minutes_ago=15),
                                                       now_iso=NOW_ISO, cfg=cfg()))
        self.assertFalse(remediation.is_ready_to_verify(self.executed(minutes_ago=3),
                                                        now_iso=NOW_ISO, cfg=cfg()))

    def test_success_when_signal_resolved(self):
        verdict = remediation.verify(self.executed(), normal())
        self.assertEqual(verdict["status"], remediation.SUCCEEDED)
        self.assertFalse(verdict["rollback"])

    def test_failure_when_signal_persists(self):
        verdict = remediation.verify(self.executed(), anomalous(keys=("traffic",)))
        self.assertEqual(verdict["status"], remediation.FAILED)
        self.assertTrue(verdict["rollback"])
        self.assertIn("traffic", verdict["note"])

    def test_scale_in_failure_when_anomaly_returns(self):
        verdict = remediation.verify(self.executed(kind=remediation.SCALE_IN, keys=()),
                                     anomalous())
        self.assertEqual(verdict["status"], remediation.FAILED)
        self.assertTrue(verdict["rollback"])

    def test_rollback_reverses_params(self):
        action = {**self.executed(), "action_id": "abc"}
        rollback = remediation.rollback_of(action, now_iso=NOW_ISO, cfg=cfg())
        self.assertEqual(rollback["kind"], remediation.SCALE_IN)
        self.assertEqual(rollback["params"]["from_replicas"], 2)
        self.assertEqual(rollback["params"]["to_replicas"], 1)
        self.assertEqual(rollback["rollback_of"], "abc")
        # 롤백은 원상복구이므로 재승인을 요구하지 않는다.
        self.assertEqual(rollback["status"], remediation.APPROVED)


class ReplanTest(unittest.TestCase):
    """재계획: 확장 실패 후 진단 결과를 근거로 추가확장 vs 롤백을 결정한다."""

    def failed_scale_out(self, to=2, keys=("saturation", "traffic")):
        return {"action_id": "orig", "kind": remediation.SCALE_OUT,
                "trigger": {"signal_keys": list(keys)},
                "params": {"service": "backend", "from_replicas": to - 1, "to_replicas": to},
                "guardrails": {}}

    def persisting(self, keys=("saturation", "traffic")):
        return {"detected_keys": list(keys), "overall_status": "위험",
                "anomalies": [{"severity": "critical"}]}

    def sat_metrics(self, cpu=88):
        return {"traffic": {"peak_cpu_percent": cpu}}

    def test_escalate_when_still_saturated_and_no_external_cause(self):
        plan = remediation.replan(self.failed_scale_out(2), self.persisting(),
                                  self.sat_metrics(88), diagnosis=None,
                                  now_iso=NOW_ISO, cfg=cfg())
        self.assertEqual(plan["decision"], "escalate")
        self.assertEqual(plan["next"]["kind"], remediation.SCALE_OUT)
        self.assertEqual(plan["next"]["params"]["to_replicas"], 3)
        self.assertTrue(plan["next"]["is_escalation"])

    def test_rollback_when_diagnosis_points_to_external_api(self):
        # 진단이 '외부 API 타임아웃'을 지목하면 확장은 무의미 → 롤백
        diag = {"status": "완료", "root_cause": "서울 외부 API가 08:15부터 상시 타임아웃"}
        plan = remediation.replan(self.failed_scale_out(2), self.persisting(),
                                  self.sat_metrics(88), diagnosis=diag,
                                  now_iso=NOW_ISO, cfg=cfg())
        self.assertEqual(plan["decision"], "rollback")
        self.assertTrue(plan["next"].get("is_rollback"))
        self.assertIn("타임아웃", plan["reason"])

    def test_rollback_at_max_replicas(self):
        # 이미 상한(4대)이면 더 확장 못 함 → 롤백
        plan = remediation.replan(self.failed_scale_out(4), self.persisting(),
                                  self.sat_metrics(90), diagnosis=None,
                                  now_iso=NOW_ISO, cfg=cfg())
        self.assertEqual(plan["decision"], "rollback")
        self.assertIn("최대 인스턴스", plan["reason"])

    def test_rollback_when_not_saturated(self):
        # 신호는 남았지만 CPU 낮고 traffic/saturation 아님 → 확장 근거 약함 → 롤백
        plan = remediation.replan(self.failed_scale_out(2, keys=("latency",)),
                                  {"detected_keys": ["api_errors"], "overall_status": "위험",
                                   "anomalies": [{"severity": "warning"}]},
                                  self.sat_metrics(30), diagnosis=None,
                                  now_iso=NOW_ISO, cfg=cfg())
        self.assertEqual(plan["decision"], "rollback")

    def test_escalation_action_is_pending_by_default(self):
        plan = remediation.replan(self.failed_scale_out(2), self.persisting(),
                                  self.sat_metrics(88), diagnosis=None,
                                  now_iso=NOW_ISO, cfg=cfg())
        self.assertEqual(plan["next"]["status"], remediation.PENDING)

    def test_escalation_auto_approved_when_configured(self):
        plan = remediation.replan(self.failed_scale_out(2), self.persisting(),
                                  self.sat_metrics(88), diagnosis=None,
                                  now_iso=NOW_ISO, cfg=cfg(auto_approve=True))
        self.assertEqual(plan["next"]["status"], remediation.APPROVED)

    def test_diagnosis_ignored_if_not_completed(self):
        # 진단이 '생략/미결'이면 근거로 쓰지 않는다(외부원인 판단 안 함)
        diag = {"status": "생략", "root_cause": "api timeout"}
        plan = remediation.replan(self.failed_scale_out(2), self.persisting(),
                                  self.sat_metrics(88), diagnosis=diag,
                                  now_iso=NOW_ISO, cfg=cfg())
        self.assertEqual(plan["decision"], "escalate")


class LifecycleTest(unittest.TestCase):

    def test_expire_stale_pending(self):
        old = {"status": remediation.PENDING,
               "created_at": (NOW - timedelta(minutes=90)).isoformat()}
        fresh = {"status": remediation.PENDING,
                 "created_at": (NOW - timedelta(minutes=5)).isoformat()}
        self.assertTrue(remediation.expire_stale(old, now_iso=NOW_ISO, cfg=cfg()))
        self.assertFalse(remediation.expire_stale(fresh, now_iso=NOW_ISO, cfg=cfg()))

    def test_approved_action_is_not_expired(self):
        approved = {"status": remediation.APPROVED,
                    "created_at": (NOW - timedelta(hours=5)).isoformat()}
        self.assertFalse(remediation.expire_stale(approved, now_iso=NOW_ISO, cfg=cfg()))

    def test_with_status_appends_history_without_mutating(self):
        action = remediation.propose(anomalous(), metrics(1), [], now_iso=NOW_ISO, cfg=cfg())
        before = len(action["history"])
        updated = remediation.with_status(action, remediation.APPROVED, "관리자 승인",
                                          now_iso=NOW_ISO, approved_by="admin@x")
        self.assertEqual(updated["status"], remediation.APPROVED)
        self.assertEqual(updated["approved_by"], "admin@x")
        self.assertEqual(len(updated["history"]), before + 1)
        # 원본은 변하지 않는다.
        self.assertEqual(action["status"], remediation.PENDING)
        self.assertEqual(len(action["history"]), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
