"""근본 원인 진단 에이전트가 사용하는 조사 도구.

진단 에이전트(diagnosis.py)의 LLM이 이 도구들을 골라 호출하며 로그를 파고든다.
도구는 **이미 조회한 로그 이벤트 리스트 위에서 in-memory로** 동작한다:
- ES를 매 도구마다 재쿼리하지 않아 빠르고, 분석 부하가 없다.
- 순수 함수라 LLM 없이 단위 테스트가 된다(결정론적).

각 도구는 (1) 실제 결과 dict와 (2) LLM에 돌려줄 사람이 읽는 요약 문자열을 함께
만든다. 요약은 토큰을 아끼려고 상위 항목만 담는다.

서드파티 의존성 없이(stdlib만) 작성한다.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def _match(event: dict[str, Any], where_field: str | None, where_value: str | None) -> bool:
    if not where_field:
        return True
    return str(event.get(where_field, "")) == str(where_value)


def _bucket(ts: Any, minutes: int) -> str:
    """@timestamp를 분 단위 버킷 문자열로 자른다. 형식: 2026-07-21T08:15."""
    s = str(ts or "")
    if len(s) < 16:
        return s
    # YYYY-MM-DDTHH:MM 까지 자른 뒤, 분을 bucket 크기로 내림한다.
    try:
        minute = int(s[14:16])
    except ValueError:
        return s[:16]
    floored = (minute // max(minutes, 1)) * max(minutes, 1)
    return f"{s[:14]}{floored:02d}"


def breakdown_by(events: list[dict[str, Any]], field: str,
                 where_field: str | None = None, where_value: str | None = None,
                 top: int = 8) -> dict[str, Any]:
    """필드 값의 분포를 센다. where로 부분집합을 먼저 거를 수 있다.

    예: breakdown_by(events, "error_code", "event_type", "API_COLLECTION")
        → {"504": 27, "429": 3, ...}
    """
    counts: Counter[str] = Counter()
    matched = 0
    for event in events:
        if not _match(event, where_field, where_value):
            continue
        matched += 1
        value = event.get(field)
        if value is None or value == "":
            continue
        counts[str(value)] += 1

    items = counts.most_common(top)
    summary = ", ".join(f"{k}={v}" for k, v in items) or "해당 값 없음"
    where_note = f" (조건 {where_field}={where_value})" if where_field else ""
    return {
        "tool": "breakdown_by",
        "field": field,
        "matched_events": matched,
        "distribution": dict(items),
        "summary": f"{field} 분포{where_note}: {summary} / 대상 {matched}건",
    }


def time_histogram(events: list[dict[str, Any]], bucket_minutes: int = 5,
                   where_field: str | None = None, where_value: str | None = None,
                   top: int = 12) -> dict[str, Any]:
    """@timestamp를 시간 버킷으로 잘라 건수를 센다. 언제 몰렸는지 본다.

    예: time_histogram(events, 5, "error_code", "504")
        → {"2026-07-21T08:15": 9, "2026-07-21T08:20": 11, ...}
    """
    buckets: Counter[str] = Counter()
    matched = 0
    for event in events:
        if not _match(event, where_field, where_value):
            continue
        matched += 1
        buckets[_bucket(event.get("@timestamp"), bucket_minutes)] += 1

    ordered = sorted(buckets.items())[-top:]
    summary = ", ".join(f"{k[11:]}={v}" for k, v in ordered) or "데이터 없음"
    where_note = f" (조건 {where_field}={where_value})" if where_field else ""
    return {
        "tool": "time_histogram",
        "bucket_minutes": bucket_minutes,
        "matched_events": matched,
        "series": dict(ordered),
        "summary": f"{bucket_minutes}분 단위 분포{where_note}: {summary}",
    }


_SAMPLE_FIELDS = ("@timestamp", "event_type", "endpoint", "http_status",
                  "error_code", "error_msg", "message", "cpu_percent",
                  "memory_percent", "requests_per_second")


def sample_events(events: list[dict[str, Any]], where_field: str | None = None,
                  where_value: str | None = None, limit: int = 5) -> dict[str, Any]:
    """조건에 맞는 실제 로그 몇 건을 그대로 본다. error_msg 등 원문 확인용."""
    samples = []
    for event in events:
        if not _match(event, where_field, where_value):
            continue
        samples.append({k: event.get(k) for k in _SAMPLE_FIELDS if event.get(k) is not None})
        if len(samples) >= limit:
            break
    where_note = f" (조건 {where_field}={where_value})" if where_field else ""
    return {
        "tool": "sample_events",
        "matched_events": len(samples),
        "samples": samples,
        "summary": f"샘플 {len(samples)}건{where_note}",
    }


def field_values(events: list[dict[str, Any]], where_field: str | None = None,
                 where_value: str | None = None) -> dict[str, Any]:
    """조건에 맞는 이벤트들이 어떤 필드를 갖고 있는지(조사 방향 잡기용)."""
    present: dict[str, int] = defaultdict(int)
    matched = 0
    for event in events:
        if not _match(event, where_field, where_value):
            continue
        matched += 1
        for key, value in event.items():
            if value not in (None, ""):
                present[key] += 1
    ordered = sorted(present.items(), key=lambda kv: -kv[1])
    return {
        "tool": "field_values",
        "matched_events": matched,
        "fields": dict(ordered),
        "summary": f"대상 {matched}건에서 관측된 필드: {', '.join(k for k, _ in ordered)}",
    }


# 도구 이름 → 함수. dispatch에서 사용한다.
TOOLS = {
    "breakdown_by": breakdown_by,
    "time_histogram": time_histogram,
    "sample_events": sample_events,
    "field_values": field_values,
}

# OpenAI function-calling 스키마. diagnosis.py가 LLM에 bind한다.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "breakdown_by",
            "description": "로그를 특정 필드 값으로 그룹핑해 분포를 센다. "
                           "예: 오류가 어떤 error_code/endpoint/http_status에 몰렸는지.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field": {"type": "string",
                              "description": "분포를 볼 필드. error_code, http_status, endpoint, event_type 등"},
                    "where_field": {"type": "string", "description": "부분집합을 거를 필드(선택)"},
                    "where_value": {"type": "string", "description": "부분집합 값(선택)"},
                },
                "required": ["field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "time_histogram",
            "description": "로그를 시간 버킷으로 잘라 건수를 센다. 문제가 언제 시작/집중됐는지 본다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bucket_minutes": {"type": "integer", "description": "버킷 크기(분). 기본 5"},
                    "where_field": {"type": "string", "description": "부분집합을 거를 필드(선택)"},
                    "where_value": {"type": "string", "description": "부분집합 값(선택)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sample_events",
            "description": "조건에 맞는 실제 로그 몇 건을 원문 그대로 본다. error_msg 확인용.",
            "parameters": {
                "type": "object",
                "properties": {
                    "where_field": {"type": "string", "description": "거를 필드(선택)"},
                    "where_value": {"type": "string", "description": "값(선택)"},
                    "limit": {"type": "integer", "description": "샘플 개수. 기본 5"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "field_values",
            "description": "조건에 맞는 이벤트가 어떤 필드를 갖고 있는지 본다. 조사 방향을 잡을 때.",
            "parameters": {
                "type": "object",
                "properties": {
                    "where_field": {"type": "string", "description": "거를 필드(선택)"},
                    "where_value": {"type": "string", "description": "값(선택)"},
                },
                "required": [],
            },
        },
    },
]


def dispatch(name: str, args: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    """도구 이름과 인자로 도구를 실행한다. 알 수 없는 도구/잘못된 인자는 오류 dict를 돌려준다."""
    func = TOOLS.get(name)
    if func is None:
        return {"tool": name, "error": f"알 수 없는 도구: {name}", "summary": f"알 수 없는 도구: {name}"}
    try:
        return func(events, **args)
    except TypeError as exc:
        return {"tool": name, "error": f"잘못된 인자: {exc}", "summary": f"도구 {name} 인자 오류"}
