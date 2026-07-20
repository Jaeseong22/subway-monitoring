"""LLM 출력 검증/병합.

프롬프트로 "grounded_analysis를 진실로 취급하라"고 부탁하는 것만으로는 모델이
severity를 뒤집거나 수치를 지어내는 것을 막을 수 없다. 결정론적 통계 판단의
신뢰성이 LLM 단계에서 소실되지 않도록 **코드 레벨에서** 강제한다.

LLM이 대체할 수 있는 것: 제목/요약/설명/근거/조치사항 등 서술 텍스트.
LLM이 대체할 수 없는 것: overall_status, severity, today_anomaly_count,
                         detected_keys, pending_signals, metric_trend 수치,
                         anomalies 목록의 개수와 심각도.

서드파티 의존성 없이(stdlib만) 작성되어 단위 테스트가 가능하다.
"""
from __future__ import annotations

import json
from typing import Any


def clean_str(value: Any, limit: int = 500) -> str | None:
    """LLM이 준 값이 실제로 쓸 만한 문자열일 때만 정규화해 반환한다."""
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] if cleaned else None


def clean_str_list(value: Any, limit: int = 10) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = [s for s in (clean_str(v) for v in value) if s]
    return items[:limit] if items else None


def merge_llm_result(grounded: dict[str, Any], llm: Any) -> dict[str, Any]:
    """LLM 출력에서 서술 텍스트만 채택하고 판정·수치는 grounded 값을 강제한다."""
    result = json.loads(json.dumps(grounded))  # 깊은 복사
    if not isinstance(llm, dict):
        return result

    latest = llm.get("latest_anomaly")
    if isinstance(latest, dict):
        for field in ("title", "summary"):
            value = clean_str(latest.get(field))
            if value:
                result["latest_anomaly"][field] = value

    detail = llm.get("selected_anomaly_detail")
    if isinstance(detail, dict):
        for field in ("title", "description"):
            value = clean_str(detail.get(field))
            if value:
                result["selected_anomaly_detail"][field] = value
        for field in ("evidence", "recommended_actions"):
            values = clean_str_list(detail.get(field))
            if values:
                result["selected_anomaly_detail"][field] = values

    # insights는 신호 개수가 통계 결과와 일치할 때만 문구를 교체한다.
    insights = llm.get("insights")
    if isinstance(insights, list) and len(insights) == len(result.get("insights", [])):
        for idx, item in enumerate(insights):
            if not isinstance(item, dict):
                continue
            for field in ("title", "summary"):
                value = clean_str(item.get(field))
                if value:
                    result["insights"][idx][field] = value

    # latest_anomaly.title을 바꿨다면 anomalies 목록의 대표 항목 제목도 맞춰준다.
    if result.get("anomalies") and result["latest_anomaly"].get("title"):
        result["anomalies"][0]["title"] = result["latest_anomaly"]["title"]

    return result
