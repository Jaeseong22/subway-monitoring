import json
import os
from datetime import datetime, time, timezone
from typing import Any, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from es_client import ElasticsearchClient
from graph import detection
from prompts.anomaly_prompt import build_anomaly_prompt


class GraphState(TypedDict, total=False):
    metrics: dict[str, Any]
    baseline: dict[str, Any]
    off_hours: bool
    result: dict[str, Any]
    result_index: str


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
        return {
            "metrics": {
                "analysis_window": {"start": None, "end": None},
                "error": str(exc),
            },
            "baseline": {},
            "off_hours": off_hours,
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
    traffic_request_count = sum(_to_int(e.get("request_count")) for e in traffic_events)
    traffic_peak_rps = max((_to_float(e.get("requests_per_second")) for e in traffic_events), default=0.0)
    traffic_peak_cpu = max((_to_float(e.get("cpu_percent")) for e in traffic_events), default=0.0)
    traffic_peak_memory = max((_to_float(e.get("memory_percent")) for e in traffic_events), default=0.0)
    traffic_peak_queue_depth = max((_to_int(e.get("queue_depth")) for e in traffic_events), default=0)
    traffic_instance_count = max((_to_int(e.get("instance_count")) for e in traffic_events), default=0)
    traffic_points = [
        {"ts": e.get("@timestamp"), "value": _to_int(e.get("request_count"))}
        for e in traffic_events
        if e.get("@timestamp") and _to_int(e.get("request_count")) > 0
    ]
    # 지연: golden 요약의 avg_elapsed_ms, 없으면 개별 요청 elapsed_ms 사용.
    traffic_latencies = [
        _to_float(e.get("avg_elapsed_ms") if e.get("avg_elapsed_ms") is not None else e.get("elapsed_ms"))
        for e in traffic_events
        if e.get("avg_elapsed_ms") is not None or e.get("elapsed_ms") is not None
    ]
    traffic_avg_elapsed = sum(traffic_latencies) / len(traffic_latencies) if traffic_latencies else 0.0
    # p95: golden 요약이 남긴 p95_elapsed_ms의 창 내 최댓값.
    traffic_peak_p95 = max(
        (_to_float(e.get("p95_elapsed_ms")) for e in traffic_events if e.get("p95_elapsed_ms") is not None),
        default=0.0,
    )

    latest_metric = metric_events[-1] if metric_events else {}
    day_of_week = str(latest_metric.get("day_of_week", ""))
    hour_of_day = str(latest_metric.get("hour_of_day", ""))

    # 기준선은 현재 시각의 시간대 + 평일/주말 기준으로 조회한다(로그가 없어도 안정적).
    baseline_hour = str(now_local.hour)
    baseline_is_weekend = "true" if now_local.weekday() >= 5 else "false"
    try:
        baseline_events = client.fetch_baseline_events(baseline_hour, baseline_is_weekend)
    except Exception:
        baseline_events = []
    # 과거 같은 시간대 표본에서 신호별 평균/표준편차 기준선을 계산한다.
    baseline = detection.compute_baseline_stats(baseline_events)

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
            "p95_elapsed_ms": traffic_peak_p95,
            "request_count": traffic_request_count,
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
                str(e.get("error_msg") or e.get("message"))
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

    return {"metrics": metrics, "baseline": baseline, "off_hours": off_hours}


def analyze_with_llm(state: GraphState) -> GraphState:
    metrics = state["metrics"]
    baseline = state["baseline"]
    off_hours = state["off_hours"]
    # 통계적 기준선 기반 결정론적 판단(근거 있는 이상탐지). rules 모드와 LLM 폴백 모두 이걸 사용한다.
    grounded = detection.evaluate(metrics, baseline, off_hours)

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
        result = json.loads(_strip_code_fences(content))
    except Exception:
        # LLM 오류/네트워크 실패/파싱 실패 시 통계 기반 결과로 폴백한다.
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
        return {"result_index": f"error:{exc}"}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("fetch_metrics", fetch_metrics)
    graph.add_node("analyze", analyze_with_llm)
    graph.add_node("store", store_result)

    graph.set_entry_point("fetch_metrics")
    graph.add_edge("fetch_metrics", "analyze")
    graph.add_edge("analyze", "store")
    graph.add_edge("store", END)

    return graph.compile()
