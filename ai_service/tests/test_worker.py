"""remediation_worker.process_once 상태 기계 테스트.

실제 ES/Docker 없이 fake client로 워커의 조치 처리 흐름을 검증한다.
특히 워커가 죽어 멈춘 조치(EXECUTING/EXECUTED)를 재기동 후 정리하는 경로를 본다.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import remediation_worker as worker  # noqa: E402
from graph import remediation  # noqa: E402

NOW = datetime.now(timezone.utc)


def cfg(**overrides):
    base = {
        "enabled": True, "auto_approve": False, "service": "backend",
        "max_replicas": 4, "min_replicas": 1, "cooldown_minutes": 15,
        "verify_after_minutes": 10, "expire_after_minutes": 60,
        "scale_in_after_normal_runs": 6, "cpu_warn": 60, "execute_timeout_minutes": 15,
    }
    base.update(overrides)
    return base


class FakeClient:
    """process_once가 부르는 인터페이스만 흉내낸다."""

    def __init__(self, actions, latest=None, latest_after_refresh=None):
        self._actions = actions
        self.updates = {}   # action_id → 마지막으로 쓴 상태
        self.saved = []     # save_action으로 새로 만든 조치들
        self._latest = latest or {"result": {}, "metrics": {}, "diagnosis": None}
        self._latest_after_refresh = latest_after_refresh
        self.refreshed = False

    def fetch_recent_actions(self, size=50):
        return list(self._actions)

    def fetch_latest_analysis(self):
        if self.refreshed and self._latest_after_refresh is not None:
            return self._latest_after_refresh
        return self._latest

    def update_action(self, action_id, action):
        self.updates[action_id] = action

    def save_action(self, action):
        self.saved.append(action)
        return f"new-{len(self.saved)}"


def ago(minutes):
    return (NOW - timedelta(minutes=minutes)).isoformat()


class WorkerStuckTest(unittest.TestCase):

    def test_stuck_executing_is_failed_on_restart(self):
        """워커가 EXECUTING에서 죽고 재기동하면, 이제 그 조치를 정리한다.

        (수정 전에는 EXECUTING을 처리하는 분기가 없어 영원히 멈춰 있었다.)
        """
        stuck = {"action_id": "a1", "status": remediation.EXECUTING,
                 "history": [{"at": ago(30), "status": remediation.EXECUTING, "note": "실행 시작"}]}
        client = FakeClient([stuck])
        handled = worker.process_once(client, cfg(), dry_run=True)
        self.assertEqual(handled, 1)
        self.assertEqual(client.updates["a1"]["status"], remediation.FAILED)

    def test_recent_executing_left_alone(self):
        running = {"action_id": "a1", "status": remediation.EXECUTING,
                   "history": [{"at": ago(3), "status": remediation.EXECUTING, "note": "실행 시작"}]}
        client = FakeClient([running])
        handled = worker.process_once(client, cfg(), dry_run=True)
        self.assertEqual(handled, 0)
        self.assertNotIn("a1", client.updates)  # 아직 실행 중일 수 있어 건드리지 않음

    def test_long_unverified_executed_is_failed(self):
        stuck = {"action_id": "a1", "status": remediation.EXECUTED, "executed_at": ago(90),
                 "history": [{"at": ago(90), "status": remediation.EXECUTED, "note": "실행 완료"}]}
        client = FakeClient([stuck])
        worker.process_once(client, cfg(), dry_run=True)
        self.assertEqual(client.updates["a1"]["status"], remediation.FAILED)

    def test_executed_ready_gets_verified(self):
        # 검증 시한(10분) 지났지만 expire(60분) 전 → 정상 검증 경로
        executed = {"action_id": "a1", "status": remediation.EXECUTED, "executed_at": ago(15),
                    "kind": remediation.SCALE_OUT, "trigger": {"signal_keys": ["traffic"]},
                    "params": {"from_replicas": 1, "to_replicas": 2},
                    "history": [{"at": ago(15), "status": remediation.EXECUTED, "note": "완료"}]}
        # 촉발 신호가 사라진 정상 결과 → SUCCEEDED
        client = FakeClient([executed], latest={"result": {"detected_keys": [], "overall_status": "정상"},
                                                "metrics": {}, "diagnosis": None})
        worker.process_once(client, cfg(), dry_run=True)
        self.assertEqual(client.updates["a1"]["status"], remediation.SUCCEEDED)

    def test_expired_pending(self):
        old = {"action_id": "a1", "status": remediation.PENDING, "created_at": ago(90)}
        client = FakeClient([old])
        worker.process_once(client, cfg(), dry_run=True)
        self.assertEqual(client.updates["a1"]["status"], remediation.EXPIRED)

    def test_approved_gets_executed_in_dry_run(self):
        approved = {"action_id": "a1", "status": remediation.APPROVED,
                    "params": {"service": "backend", "to_replicas": 2},
                    "history": [{"at": ago(1), "status": remediation.APPROVED, "note": "승인"}]}
        client = FakeClient([approved])
        worker.process_once(client, cfg(), dry_run=True)
        # dry-run이면 실행 성공으로 간주 → EXECUTED
        self.assertEqual(client.updates["a1"]["status"], remediation.EXECUTED)

    def test_verify_failure_triggers_replan(self):
        executed = {"action_id": "a1", "status": remediation.EXECUTED, "executed_at": ago(15),
                    "kind": remediation.SCALE_OUT, "trigger": {"signal_keys": ["saturation", "traffic"]},
                    "params": {"service": "backend", "from_replicas": 1, "to_replicas": 2},
                    "history": [{"at": ago(15), "status": remediation.EXECUTED, "note": "완료"}]}
        # 신호가 지속 + CPU 포화 → 재계획이 추가확장(escalate) 조치를 생성
        client = FakeClient([executed], latest={
            "result": {"detected_keys": ["saturation", "traffic"], "overall_status": "위험",
                       "anomalies": [{"severity": "critical"}]},
            "metrics": {"traffic": {"peak_cpu_percent": 90}}, "diagnosis": None})
        worker.process_once(client, cfg(), dry_run=True)
        self.assertEqual(client.updates["a1"]["status"], remediation.FAILED)
        self.assertEqual(len(client.saved), 1)  # 재계획 조치 생성됨
        self.assertTrue(client.saved[0].get("is_escalation"))


class WorkerVerifyFreshnessTest(unittest.TestCase):
    """검증은 '실행 이후'의 분석 결과로만 한다.

    하루 2회 고정 시각 모드에서는 검증 시점에 새 결과가 없다. 촉발 결과로 검증하면
    촉발 신호가 당연히 남아 있어 매번 롤백된다.
    """

    def setUp(self):
        self._orig_refresh = worker.refresh_analysis

    def tearDown(self):
        worker.refresh_analysis = self._orig_refresh

    @staticmethod
    def executed():
        return {"action_id": "a1", "status": remediation.EXECUTED, "executed_at": ago(15),
                "kind": remediation.SCALE_OUT, "trigger": {"signal_keys": ["traffic"]},
                "params": {"service": "backend", "from_replicas": 1, "to_replicas": 2},
                "history": [{"at": ago(15), "status": remediation.EXECUTED, "note": "완료"}]}

    def test_stale_result_triggers_refresh_then_verifies_with_fresh_one(self):
        # 최신 결과가 실행 '이전'(촉발 결과, 이상 지속) → 그대로 쓰면 FAILED+롤백이 됐을 것
        stale = {"result": {"detected_keys": ["traffic"], "overall_status": "위험"},
                 "metrics": {}, "diagnosis": None, "generated_at": ago(30)}
        fresh = {"result": {"detected_keys": [], "overall_status": "정상"},
                 "metrics": {}, "diagnosis": None, "generated_at": ago(0)}
        client = FakeClient([self.executed()], latest=stale, latest_after_refresh=fresh)

        def fake_refresh():
            client.refreshed = True
            return True
        worker.refresh_analysis = fake_refresh

        worker.process_once(client, cfg(), dry_run=False)
        self.assertTrue(client.refreshed)
        self.assertEqual(client.updates["a1"]["status"], remediation.SUCCEEDED)
        self.assertEqual(client.saved, [])  # 롤백이 만들어지지 않았다

    def test_refresh_failure_defers_verification(self):
        stale = {"result": {"detected_keys": ["traffic"], "overall_status": "위험"},
                 "metrics": {}, "diagnosis": None, "generated_at": ago(30)}
        client = FakeClient([self.executed()], latest=stale)
        worker.refresh_analysis = lambda: False
        worker.process_once(client, cfg(), dry_run=False)
        # 판정하지 않고 다음 주기로 넘긴다
        self.assertNotIn("a1", client.updates)

    def test_dry_run_verifies_without_refresh(self):
        stale = {"result": {"detected_keys": [], "overall_status": "정상"},
                 "metrics": {}, "diagnosis": None}  # generated_at 없음
        client = FakeClient([self.executed()], latest=stale)
        called = []
        worker.refresh_analysis = lambda: called.append(1) or True
        worker.process_once(client, cfg(), dry_run=True)
        self.assertEqual(called, [])
        self.assertEqual(client.updates["a1"]["status"], remediation.SUCCEEDED)

    def test_analysis_is_post_execution(self):
        action = {"executed_at": ago(10)}
        self.assertTrue(remediation.analysis_is_post_execution(action, {"generated_at": ago(5)}))
        self.assertFalse(remediation.analysis_is_post_execution(action, {"generated_at": ago(20)}))
        self.assertFalse(remediation.analysis_is_post_execution(action, {}))
        self.assertFalse(remediation.analysis_is_post_execution({}, {"generated_at": ago(5)}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
