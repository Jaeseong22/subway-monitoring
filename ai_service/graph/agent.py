import json
import logging
import os
from datetime import datetime, time, timedelta, timezone
from typing import Any, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from es_client import ElasticsearchClient
from graph import detection, remediation
from graph.llm_merge import merge_llm_result
from prompts.anomaly_prompt import build_anomaly_prompt


LOGGER = logging.getLogger("ai-service")


class GraphState(TypedDict, total=False):
    metrics: dict[str, Any]
    baseline: dict[str, Any]
    off_hours: bool
    recent_keys: list[list[str]]
    recent_actions: list[dict[str, Any]] | None
    result: dict[str, Any]
    result_index: str
    proposed_action_id: str | None


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _mean(values) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def _count_api_instances(golden_events: list[dict[str, Any]]) -> int:
    """가동 중인 **API 인스턴스** 수.

    두 가지를 걸러내야 정확해진다:
    1. 수집 전용 프로세스(collector)도 같은 앱이라 골든시그널을 남기지만, 로드밸런서
       뒤에 있지 않으므로 확장 대상이 아니다. `instance_role`로 제외한다.
    2. 재시작·축소된 인스턴스의 지표가 분석 창(수 분)에 남아 있어 그대로 세면 과다 집계된다.
       가장 최근 1분 버킷에 지표를 남긴 인스턴스만 "지금 살아 있는" 것으로 본다.
    """
    api_events = [e for e in golden_events
                  if str(e.get("instance_role") or "api").lower() != "collector"]
    if not api_events:
        return 0

    # 분 단위(YYYY-MM-DDTHH:MM)로 잘라 가장 최근 버킷에 살아 있던 인스턴스만 센다.
    stamped = [e for e in api_events if e.get("@timestamp") and e.get("instance_id")]
    if stamped:
        latest_bucket = max(str(e["@timestamp"])[:16] for e in stamped)
        live = {str(e["instance_id"]) for e in stamped
                if str(e["@timestamp"])[:16] == latest_bucket}
        if live:
            return len(live)

    # 타임스탬프가 없으면 창 전체의 서로 다른 id 개수로 대체한다.
    ids = {str(e["instance_id"]) for e in api_events if e.get("instance_id")}
    if ids:
        return len(ids)

    # instance_id를 남기지 않는 구버전 로그와의 호환.
    return max((_to_int(e.get("instance_count")) for e in api_events), default=0)


def _sanitize(text: Any, limit: int = 300) -> str:
    """로그 유래 문자열을 프롬프트에 넣기 전에 정리한다.

    error_msg는 외부 API 응답에서 오므로 LLM 지시를 오염시키는 문자열이 섞일 수 있다.
    개행/코드펜스를 제거하고 길이를 제한해 프롬프트 인젝션 표면을 줄인다.
    """
    cleaned = " ".join(str(text).split()).replace("```", "")
    return cleaned[:limit]


def _is_off_hours(now: datetime) -> bool:
    start_raw = os.getenv("OFF_HOURS_START", "02:00")
    end_raw = os.getenv("OFF_HOURS_END", "05:00")
    start = time.fromisoformat(start_raw)
    end = time.fromisoformat(end_raw)
    now_time = now.time()
    return start <= now_time < end


def fetch_metrics(state: GraphState) -> GraphState:
    lookback = int(os.getenv("LOOKBACK_MINUTES", "30"))
    now_local = datetime.now()
    off_hours = _is_off_hours(now_local)

    try:
        client = ElasticsearchClient()
        window, events = client.fetch_recent_events(lookback)
    except Exception as exc:
        LOGGER.error("Elasticsearch 로그 조회 실패: %s", exc)
        return {
            "metrics": {
                "analysis_window": {"start": None, "end": None},
                "error": str(exc),
            },
            "baseline": {},
            "off_hours": off_hours,
            "recent_keys": [],
        }

    api_events = [e for e in events if e.get("event_type") == "API_COLLECTION"]
    traffic_events = [e for e in events if e.get("event_type") == "TRAFFIC"]
    scheduler_events = [e for e in events if e.get("event_type") == "SCHEDULER"]
    system_error_events = [e for e in events if e.get("event_type") == "SYSTEM_FETCH_ERROR"]
    metric_events = [e for e in events if e.get("event_type") == "METRIC_COLLECTION"]
    congestion_events = [e for e in events if e.get("event_type") == "STATION_CONGESTION_ALERT"]

    api_total = len(api_events)
    api_failed_events = [e for e in api_events if e.get("success") == "false"]
    api_error = len(api_failed_events)
    traffic_total = len(traffic_events)
    traffic_error = len([e for e in traffic_events if e.get("success") == "false"])
    scheduler_total = len(scheduler_events)
    failed_scheduler_events = [e for e in scheduler_events if e.get("success") == "false"]
    scheduler_error = len(failed_scheduler_events) + len(system_error_events)
    # golden 요약(1분 집계)과 개별 요청 로그를 분리한다. 두 종류를 한 리스트에서
    # 평균 내면 "집계값과 원시값의 평균"이라는 통계적으로 의미 없는 수가 나온다.
    golden_events = [e for e in traffic_events if e.get("event_name") == "golden_signals_summary"]
    request_events = [e for e in traffic_events if e.get("event_name") != "golden_signals_summary"]

    traffic_request_count = (sum(_to_int(e.get("request_count")) for e in golden_events)
                             if golden_events else len(request_events))
    # 창 '평균'과 창 '피크'를 모두 계산한다. detection은 평균끼리/피크끼리 비교한다.
    #
    # rps는 **인스턴스당** 값이다(각 인스턴스가 자기 지표를 1분마다 남긴다).
    # 클러스터 합계로 바꾸면 인스턴스를 늘린 직후 baseline(과거 인스턴스당 값) 대비
    # 배수가 튀어 확장 자체가 트래픽 급증으로 오탐된다. 인스턴스당 부하는 확장 판단의
    # 기준으로도 적절하므로(HPA의 target-per-pod와 같은 관점) 인스턴스당 값을 유지한다.
    traffic_mean_rps = _mean(_to_float(e.get("requests_per_second")) for e in golden_events)
    traffic_peak_rps = max((_to_float(e.get("requests_per_second")) for e in golden_events), default=0.0)
    traffic_peak_cpu = max((_to_float(e.get("cpu_percent")) for e in golden_events), default=0.0)
    traffic_peak_memory = max((_to_float(e.get("memory_percent")) for e in golden_events), default=0.0)
    traffic_peak_queue_depth = max((_to_int(e.get("queue_depth")) for e in golden_events), default=0)
    traffic_instance_count = _count_api_instances(golden_events)
    traffic_points = [
        {"ts": e.get("@timestamp"), "value": _to_int(e.get("request_count"))}
        for e in golden_events
        if e.get("@timestamp") and _to_int(e.get("request_count")) > 0
    ]
    # 지연: golden 요약의 avg_elapsed_ms를 우선 사용하고, 없으면 개별 요청 elapsed_ms로 폴백.
    if golden_events:
        traffic_avg_elapsed = _mean(_to_float(e.get("avg_elapsed_ms")) for e in golden_events
                                    if e.get("avg_elapsed_ms") is not None)
        traffic_peak_elapsed = max((_to_float(e.get("avg_elapsed_ms")) for e in golden_events
                                    if e.get("avg_elapsed_ms") is not None), default=0.0)
    else:
        traffic_avg_elapsed = _mean(_to_float(e.get("elapsed_ms")) for e in request_events
                                    if e.get("elapsed_ms") is not None)
        traffic_peak_elapsed = max((_to_float(e.get("elapsed_ms")) for e in request_events
                                    if e.get("elapsed_ms") is not None), default=0.0)
    # p95: 창 평균(기준선 평균과 비교용)과 창 최댓값(기준선 p99와 비교용)을 함께 보관.
    p95_values = [_to_float(e.get("p95_elapsed_ms")) for e in golden_events
                  if e.get("p95_elapsed_ms") is not None]
    traffic_mean_p95 = _mean(p95_values)
    traffic_peak_p95 = max(p95_values, default=0.0)

    # ES는 정렬을 지정하지 않으면 순서를 보장하지 않는다. 타임스탬프로 최신 문서를 고른다.
    latest_metric = max(metric_events, key=lambda e: str(e.get("@timestamp") or ""), default={}) \
        if metric_events else {}
    day_of_week = str(latest_metric.get("day_of_week", ""))
    hour_of_day = str(latest_metric.get("hour_of_day", ""))

    # 기준선은 현재 시각의 시간대 + 평일/주말 기준으로 조회한다(로그가 없어도 안정적).
    # 분석 창(직전 lookback분)의 중앙 시각을 기준으로 시간 버킷을 고른다.
    # now.hour를 쓰면 08:00 실행 시 07:30~08:00 데이터를 hour=8 기준선과 비교하게 된다.
    window_mid = now_local - timedelta(minutes=lookback / 2)
    baseline_hour = str(window_mid.hour)
    baseline_is_weekend = "true" if window_mid.weekday() >= 5 else "false"
    try:
        baseline_events = client.fetch_baseline_events(baseline_hour, baseline_is_weekend)
    except Exception as exc:
        LOGGER.warning("baseline 조회 실패 — 절대 임계값으로 판단합니다: %s", exc)
        baseline_events = []
    # 과거 같은 시간대 표본에서 신호별 평균/표준편차/분위수 기준선을 계산한다.
    baseline = detection.compute_baseline_stats(baseline_events)

    # 이력 조회: 디바운스(연속 N회)와 축소 판단(연속 정상 M회)에 함께 쓴다.
    consecutive_n = int(os.getenv("ANOMALY_CONSECUTIVE_N", "2"))
    remediation_cfg = remediation.config()
    history_size = max(consecutive_n - 1, remediation_cfg["scale_in_after_normal_runs"], 1)
    try:
        recent_keys = client.fetch_recent_detected_keys(history_size)
    except Exception as exc:
        LOGGER.warning("이전 분석 이력 조회 실패 — 디바운스를 건너뜁니다: %s", exc)
        recent_keys = []

    try:
        recent_actions = client.fetch_recent_actions()
    except Exception as exc:
        LOGGER.warning("자동 대응 이력 조회 실패 — 조치를 제안하지 않습니다: %s", exc)
        recent_actions = None  # None = 조회 실패(제안 보류), [] = 이력 없음(제안 가능)

    metrics = {
        "analysis_window": {"start": window.start.isoformat(), "end": window.end.isoformat()},
        "api": {
            "total": api_total,
            "error": api_error,
            "error_rate": api_error / api_total if api_total else 0.0,
            "avg_elapsed_ms": sum(_to_float(e.get("elapsed_ms")) for e in api_events) / api_total if api_total else 0.0,
            "max_elapsed_ms": max((_to_float(e.get("elapsed_ms")) for e in api_events), default=0.0),
            "endpoints": sorted({str(e.get("endpoint")) for e in api_events if e.get("endpoint")}),
            "error_codes": sorted({str(e.get("error_code")) for e in api_failed_events if e.get("error_code")}),
            "http_statuses": sorted({str(e.get("http_status")) for e in api_failed_events if e.get("http_status")}),
        },
        "traffic": {
            "total": traffic_total,
            "error": traffic_error,
            "error_rate": traffic_error / traffic_total if traffic_total else 0.0,
            "avg_elapsed_ms": traffic_avg_elapsed,
            "peak_elapsed_ms": traffic_peak_elapsed,
            # p95_elapsed_ms는 창 '평균'(기준선 평균과 비교), peak_*는 창 '최댓값'(기준선 p99와 비교)
            "p95_elapsed_ms": traffic_mean_p95,
            "peak_p95_elapsed_ms": traffic_peak_p95,
            "request_count": traffic_request_count,
            "requests_per_second": traffic_mean_rps,
            "peak_requests_per_second": traffic_peak_rps,
            "peak_cpu_percent": traffic_peak_cpu,
            "peak_memory_percent": traffic_peak_memory,
            "peak_queue_depth": traffic_peak_queue_depth,
            "instance_count": traffic_instance_count,
            "points": traffic_points,
        },
        "scheduler": {
            "total": scheduler_total,
            "error": scheduler_error,
            "error_rate": scheduler_error / scheduler_total if scheduler_total else 0.0,
            "avg_duration_ms": sum(_to_float(e.get("duration_ms")) for e in scheduler_events) / scheduler_total if scheduler_total else 0.0,
            "error_messages": [
                _sanitize(e.get("error_msg") or e.get("message"))
                for e in failed_scheduler_events + system_error_events
                if e.get("error_msg") or e.get("message")
            ][:3],
        },
        "collection": {
            "up_count": _to_int(latest_metric.get("up_count")),
            "down_count": _to_int(latest_metric.get("down_count")),
            "fetched_total": _to_int(latest_metric.get("fetched_total")),
            "line1_saved": _to_int(latest_metric.get("line1_saved")),
            "duration_ms": _to_int(latest_metric.get("duration_ms")),
            "time_category": latest_metric.get("time_category"),
            "day_of_week": day_of_week,
            "hour_of_day": hour_of_day,
        },
        "congestion_alerts": {
            "count": len(congestion_events),
            "stations": [e.get("congestion_station") for e in congestion_events if e.get("congestion_station")],
        },
    }

    return {"metrics": metrics, "baseline": baseline, "off_hours": off_hours,
            "recent_keys": recent_keys, "recent_actions": recent_actions}


def analyze_with_llm(state: GraphState) -> GraphState:
    metrics = state["metrics"]
    baseline = state["baseline"]
    off_hours = state["off_hours"]
    # 통계적 기준선 기반 결정론적 판단(근거 있는 이상탐지). rules 모드와 LLM 폴백 모두 이걸 사용한다.
    grounded = detection.evaluate(metrics, baseline, off_hours,
                                  recent_keys=state.get("recent_keys"))

    if os.getenv("ANALYSIS_MODE", "llm").lower() == "rules":
        return {"result": grounded}

    context = {
        "metrics": metrics,
        "baseline": baseline,
        "off_hours": off_hours,
        # LLM에 근거 있는 사전 판단을 함께 제공해 설명 품질을 높인다.
        "grounded_analysis": grounded,
    }
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # response_format=json_object로 모델이 순수 JSON만 반환하도록 강제한다.
    llm = ChatOpenAI(
        model=model_name,
        temperature=0.2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
    prompt = build_anomaly_prompt(context)
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(_strip_code_fences(content))
        # LLM은 서술 텍스트만 바꿀 수 있다. 판정/수치는 통계 결과로 강제한다.
        result = merge_llm_result(grounded, parsed)
    except Exception as exc:
        # LLM 오류/네트워크 실패/파싱 실패 시 통계 기반 결과로 폴백한다.
        LOGGER.warning("LLM 분석 실패 — 통계 기반 결과를 사용합니다: %s", exc)
        result = grounded

    return {"result": result}




def _strip_code_fences(text: str) -> str:
    """LLM 응답이 ```json ... ``` 코드펜스로 감싸져 있어도 안전하게 JSON 본문만 추출한다."""
    t = str(text).strip()
    if t.startswith("```"):
        newline = t.find("\n")
        if newline != -1:
            t = t[newline + 1:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def store_result(state: GraphState) -> GraphState:
    result = state.get("result", {})
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "@timestamp": generated_at,
        "generated_at": generated_at,
        "analysis_window": state.get("metrics", {}).get("analysis_window"),
        "off_hours": state.get("off_hours"),
        "metrics": state.get("metrics", {}),
        "baseline": state.get("baseline", {}),
        "result": result,
    }
    try:
        client = ElasticsearchClient()
        resp = client.save_anomaly_result(payload)
        return {"result_index": resp.get("_id")}
    except Exception as exc:
        LOGGER.error("이상탐지 결과 저장 실패: %s", exc)
        return {"result_index": f"error:{exc}"}


def _normal_streak(recent_keys: list[list[str]] | None) -> int:
    """최근 실행부터 연속으로 아무 신호도 감지되지 않은 횟수."""
    streak = 0
    for keys in recent_keys or []:
        if keys:
            break
        streak += 1
    return streak


def propose_remediation(state: GraphState) -> GraphState:
    """탐지 결과로부터 자동 대응 조치를 제안한다(실행하지 않음).

    제안은 PENDING으로 저장되고 관리자가 승인해야 실행된다. 실제 실행과 검증은
    별도 워커(`remediation_worker.py`)가 담당한다 — 분석 프로세스가 인프라를
    직접 조작하지 않도록 권한을 분리한다.
    """
    result = state.get("result", {}) or {}
    recent_actions = state.get("recent_actions")
    if recent_actions is None:
        # 이력 조회에 실패했다면 중복 조치를 낼 위험이 있으므로 제안하지 않는다.
        return {"proposed_action_id": None}

    cfg = remediation.config()
    if not cfg["enabled"]:
        return {"proposed_action_id": None}

    action = remediation.propose(
        result=result,
        metrics=state.get("metrics", {}) or {},
        recent_actions=recent_actions,
        normal_streak=_normal_streak(state.get("recent_keys")),
        cfg=cfg,
    )
    if action is None:
        return {"proposed_action_id": None}

    if action.get("blocked"):
        # 상한 도달 등 자동으로는 대응할 수 없는 상황. 기록만 남기고 실행 대상으로 두지 않는다.
        action = remediation.with_status(action, remediation.FAILED, action["reason"])
    elif cfg["auto_approve"]:
        action = remediation.with_status(action, remediation.APPROVED,
                                         "REMEDIATION_AUTO_APPROVE=true — 승인 없이 실행 대기")

    try:
        client = ElasticsearchClient()
        action_id = client.save_action(action)
    except Exception as exc:
        LOGGER.error("자동 대응 제안 저장 실패: %s", exc)
        return {"proposed_action_id": None}

    LOGGER.info("자동 대응 제안 생성 id=%s kind=%s status=%s %s→%s",
                action_id, action["kind"], action["status"],
                action["params"]["from_replicas"], action["params"]["to_replicas"])
    return {"proposed_action_id": action_id}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("fetch_metrics", fetch_metrics)
    graph.add_node("analyze", analyze_with_llm)
    graph.add_node("store", store_result)
    graph.add_node("remediate", propose_remediation)

    graph.set_entry_point("fetch_metrics")
    graph.add_edge("fetch_metrics", "analyze")
    graph.add_edge("analyze", "store")
    graph.add_edge("store", "remediate")
    graph.add_edge("remediate", END)

    return graph.compile()
