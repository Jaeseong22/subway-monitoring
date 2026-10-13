"""llm_retry 단위 테스트. 실제 대기·네트워크 없이 백오프 동작을 검증한다."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import llm_retry  # noqa: E402


class FakeRateLimit(Exception):
    """OpenAI 호환 429를 흉내낸다."""

    def __init__(self, message, status_code=429):
        super().__init__(message)
        self.status_code = status_code


GEMINI_429 = ("Error code: 429 - [{'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED', "
              "'message': 'You exceeded your current quota. Please retry in 56.5s.', "
              "'details': [{'@type': '...RetryInfo', 'retryDelay': '56s'}]}}]")


def cfg(**over):
    base = {"max_attempts": 4, "base_delay": 5, "max_delay": 75}
    base.update(over)
    return base


class SuggestedDelayTest(unittest.TestCase):

    def test_parses_retry_in_seconds(self):
        self.assertAlmostEqual(llm_retry.suggested_delay(FakeRateLimit(GEMINI_429)), 56.5)

    def test_parses_retry_delay_field(self):
        exc = FakeRateLimit("boom {'retryDelay': '12s'}")
        self.assertAlmostEqual(llm_retry.suggested_delay(exc), 12.0)

    def test_none_when_absent(self):
        self.assertIsNone(llm_retry.suggested_delay(FakeRateLimit("429 quota exceeded")))


class CallWithRetryTest(unittest.TestCase):

    def test_returns_value_without_retry(self):
        slept = []
        self.assertEqual(
            llm_retry.call_with_retry(lambda: "ok", cfg=cfg(), sleep=slept.append), "ok")
        self.assertEqual(slept, [])

    def test_retries_then_succeeds_waiting_server_delay(self):
        slept = []
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise FakeRateLimit(GEMINI_429)
            return "ok"

        self.assertEqual(llm_retry.call_with_retry(flaky, cfg=cfg(), sleep=slept.append), "ok")
        self.assertEqual(calls["n"], 2)
        self.assertEqual(len(slept), 1)
        self.assertAlmostEqual(slept[0], 57.0)  # 56.5 + 여유 0.5

    def test_exponential_backoff_when_server_gives_no_delay(self):
        slept = []

        def always():
            raise FakeRateLimit("429 rate limit")

        with self.assertRaises(FakeRateLimit):
            llm_retry.call_with_retry(always, cfg=cfg(max_attempts=3), sleep=slept.append)
        self.assertEqual(len(slept), 2)          # 3회 시도 = 2회 대기
        self.assertGreater(slept[1], slept[0])   # 5s → 10s 증가

    def test_gives_up_when_delay_exceeds_cap(self):
        slept = []

        def always():
            raise FakeRateLimit("429 please retry in 600s")

        with self.assertRaises(FakeRateLimit):
            llm_retry.call_with_retry(always, cfg=cfg(), sleep=slept.append)
        self.assertEqual(slept, [])  # 기다리지 않고 바로 포기

    def test_non_rate_limit_error_is_not_retried(self):
        slept = []
        calls = {"n": 0}

        def boom():
            calls["n"] += 1
            raise ValueError("잘못된 요청")

        with self.assertRaises(ValueError):
            llm_retry.call_with_retry(boom, cfg=cfg(), sleep=slept.append)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(slept, [])

    def test_attempts_zero_disables_retry(self):
        calls = {"n": 0}

        def always():
            calls["n"] += 1
            raise FakeRateLimit(GEMINI_429)

        with self.assertRaises(FakeRateLimit):
            llm_retry.call_with_retry(always, cfg=cfg(max_attempts=0), sleep=lambda _: None)
        self.assertEqual(calls["n"], 1)

    def test_detects_rate_limit_without_status_code(self):
        """status_code 속성이 없는 예외도 본문으로 판별한다."""
        slept = []
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("RESOURCE_EXHAUSTED: retry in 3s")
            return "ok"

        self.assertEqual(llm_retry.call_with_retry(flaky, cfg=cfg(), sleep=slept.append), "ok")
        self.assertAlmostEqual(slept[0], 3.5)



class DailyQuotaTest(unittest.TestCase):
    """일일 할당량 소진은 기다려도 안 풀리므로 즉시 포기한다."""

    DAILY = ("Error code: 429 - [{'error': {'status': 'RESOURCE_EXHAUSTED', "
             "'message': 'You exceeded your current quota. Please retry in 56.5s.', "
             "'details': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', "
             "'quotaValue': '20'}]}}]")

    def test_detects_daily_quota(self):
        self.assertTrue(llm_retry.is_daily_quota(FakeRateLimit(self.DAILY)))
        self.assertFalse(llm_retry.is_daily_quota(FakeRateLimit(GEMINI_429)))

    def test_daily_quota_is_not_retried(self):
        slept = []
        calls = {"n": 0}

        def always():
            calls["n"] += 1
            raise FakeRateLimit(self.DAILY)

        with self.assertRaises(FakeRateLimit):
            llm_retry.call_with_retry(always, cfg=cfg(), sleep=slept.append)
        self.assertEqual(calls["n"], 1)   # 재시도 안 함
        self.assertEqual(slept, [])       # 기다리지 않음

if __name__ == "__main__":
    unittest.main(verbosity=2)
