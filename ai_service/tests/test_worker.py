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

    def __init__(self, actions, latest=None):
        self._actions = actions
        self.updates = {}   # action_id → 마지막으로 쓴 상태
        self.saved = []     # save_action으로 새로 만든 조치들
        self._latest = latest or {"result": {}, "metrics": {}, "diagnosis": None}

    def fetch_recent_actions(self, size=50):
        return list(self._actions)

    def fetch_latest_analysis(self):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
