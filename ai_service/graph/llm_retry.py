"""LLM 호출 재시도 — 무료 티어의 분당 요청 제한(429)을 흡수한다.

검증 패널은 심사관 3명을 연속으로 부르고, 진단 에이전트는 최대 6스텝을 연속으로 부른다.
이상이 한 번 확정되면 수 초 안에 8~10회가 몰리는데, 무료 티어(Gemini 등)는 분당 요청
수를 제한하므로 그중 뒷부분이 429로 실패한다. 실패하면 검증 패널은 그 렌즈를 기권 처리하고
진단은 중단되므로, 판정이 "모델이 그렇게 판단해서"가 아니라 "호출이 막혀서" 달라진다.

서버가 알려주는 재시도 대기(retryDelay/Retry-After)를 우선 따르고, 없으면 지수 백오프한다.
서드파티 의존성 없이(stdlib만) 작성해 단위 테스트가 가능하다.
"""
from __future__ import annotations

import logging
import os
import random
import re
import time
from typing import Any, Callable, TypeVar

LOGGER = logging.getLogger("ai-service")

T = TypeVar("T")

# 본문/헤더에서 서버가 제시한 대기 시간을 찾는다.
# Gemini: "Please retry in 56.5s" / {"retryDelay": "56s"} , OpenAI: Retry-After 헤더
_DELAY_PATTERNS = (
    re.compile(r"retry in ([\d.]+)\s*s", re.I),
    re.compile(r"'retryDelay':\s*'([\d.]+)s'"),
    re.compile(r'"retryDelay":\s*"([\d.]+)s"'),
)


def is_daily_quota(exc: Exception) -> bool:
    """하루 단위 할당량 소진인지. 이건 기다려도 그날 안에는 풀리지 않는다.

    Gemini 무료 티어는 모델마다 일일 한도가 다르다(예: 최신 flash는 20회/일, lite 계열은
    훨씬 넉넉). 서버는 일일 소진에도 "retry in 56s"를 주므로, 그대로 믿고 재시도하면
    분석 한 번에 수십 분을 헛되이 기다린다. quotaId로 구분해 즉시 포기한다.
    """
    text = str(exc)
    return "PerDay" in text or "per day" in text.lower()


def _is_rate_limited(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if status == 429:
        return True
    text = str(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "rate limit" in text.lower()


def suggested_delay(exc: Exception) -> float | None:
    """서버가 알려준 재시도 대기(초). 없으면 None."""
    text = str(exc)
    for pattern in _DELAY_PATTERNS:
        found = pattern.search(text)
        if found:
            try:
                return float(found.group(1))
            except ValueError:
                continue
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers:
        raw = headers.get("retry-after") or headers.get("Retry-After")
        if raw:
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None
    return None


def config() -> dict[str, Any]:
    def _int(key: str, default: str) -> int:
        try:
            return int(os.getenv(key, default))
        except ValueError:
            return int(default)

    return {
        # 0이면 재시도하지 않는다(유료 티어나 테스트에서 끄고 싶을 때).
        "max_attempts": _int("LLM_RETRY_ATTEMPTS", "4"),
        "base_delay": _int("LLM_RETRY_BASE_SECONDS", "5"),
        # 서버가 제시한 대기가 이보다 길면 포기한다. 분석 주기를 넘겨 밀리는 것보다 낫다.
        "max_delay": _int("LLM_RETRY_MAX_SECONDS", "75"),
    }


def call_with_retry(fn: Callable[[], T], *, what: str = "LLM 호출",
                    cfg: dict[str, Any] | None = None,
                    sleep: Callable[[float], None] = time.sleep) -> T:
    """fn()을 호출하되 429면 대기 후 재시도한다. 다른 예외는 그대로 올린다."""
    cfg = cfg or config()
    attempts = max(1, cfg["max_attempts"])
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if not _is_rate_limited(exc) or attempt == attempts:
                raise
            if is_daily_quota(exc):
                LOGGER.warning("%s 일일 할당량 소진 — 재시도해도 풀리지 않으므로 포기합니다.", what)
                raise
            delay = suggested_delay(exc)
            if delay is None:
                # 지수 백오프 + 지터. 여러 렌즈가 동시에 깨어나 다시 몰리는 것을 막는다.
                delay = cfg["base_delay"] * (2 ** (attempt - 1)) + random.uniform(0, 1)
            if delay > cfg["max_delay"]:
                LOGGER.warning("%s 요청 제한 — 대기 %.0fs가 상한(%ss)을 넘어 포기합니다.",
                               what, delay, cfg["max_delay"])
                raise
            LOGGER.info("%s 요청 제한(429) — %.0fs 대기 후 재시도 (%d/%d)",
                        what, delay, attempt, attempts - 1)
            sleep(delay + 0.5)  # 서버 시계와의 오차를 감안해 약간 더 기다린다
    raise AssertionError("도달할 수 없음")
