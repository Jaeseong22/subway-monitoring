import json
import os
from datetime import datetime, time, timezone
from typing import Any, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from es_client import ElasticsearchClient
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

    latest_metric = metric_events[-1] if metric_events else {}
    day_of_week = str(latest_metric.get("day_of_week", ""))
    hour_of_day = str(latest_metric.get("hour_of_day", ""))

    baseline_events = client.fetch_baseline_events(day_of_week, hour_of_day) if day_of_week and hour_of_day else []

    baseline = {
        "sample_count": len(baseline_events),
        "avg_fetched_total": 0.0,
        "avg_line1_saved": 0.0,
        "avg_duration_ms": 0.0,
    }
    if baseline_events:
        baseline["avg_fetched_total"] = sum(_to_float(e.get("fetched_total")) for e in baseline_events) / len(baseline_events)
        baseline["avg_line1_saved"] = sum(_to_float(e.get("line1_saved")) for e in baseline_events) / len(baseline_events)
        baseline["avg_duration_ms"] = sum(_to_float(e.get("duration_ms")) for e in baseline_events) / len(baseline_events)

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
            "avg_elapsed_ms": sum(_to_float(e.get("elapsed_ms")) for e in traffic_events) / traffic_total if traffic_total else 0.0,
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
    context = {
        "metrics": state["metrics"],
        "baseline": state["baseline"],
        "off_hours": state["off_hours"],
    }
    if os.getenv("ANALYSIS_MODE", "llm").lower() == "rules":
        return {"result": fallback_result(context)}

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0.2)
    prompt = build_anomaly_prompt(context)
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        result = json.loads(content)
    except Exception:
        result = fallback_result(context)

    return {"result": result}


def fallback_result(context: dict[str, Any]) -> dict[str, Any]:
    metrics = context.get("metrics", {})
    api = metrics.get("api", {})
    traffic = metrics.get("traffic", {})
    scheduler = metrics.get("scheduler", {})
    api_error_rate = api.get("error_rate", 0.0)
    scheduler_error = scheduler.get("error", 0)
    traffic_requests = traffic.get("request_count", 0)
    traffic_threshold = int(os.getenv("TRAFFIC_REQUEST_THRESHOLD", "1000"))
    now = datetime.now(timezone.utc).isoformat()
    evidence: list[str] = []
    actions: list[str] = []
    trend_label = "API 오류율 (%)"
    trend_points = [{"ts": now, "value": api_error_rate * 100, "baseline": 20}]

    if api_error_rate >= 0.2:
        status = "위험"
        severity = "critical"
        title = "서울 실시간 도착 API 응답 장애"
        summary = (
            f"도착 API 요청 {api.get('total', 0)}건 중 {api.get('error', 0)}건이 실패해 "
            f"오류율 {api_error_rate * 100:.1f}%가 위험 임계치 20%를 초과했습니다."
        )
        evidence = [
            f"오류율 {api_error_rate * 100:.1f}% (위험 임계치 20%)",
            f"평균 응답 {api.get('avg_elapsed_ms', 0):.0f}ms / 최대 응답 {api.get('max_elapsed_ms', 0):.0f}ms",
            f"대상 API: {', '.join(api.get('endpoints', [])) or '실시간 도착 API'}",
            f"응답 코드: {', '.join(api.get('http_statuses', [])) or '미기록'} / 원인 코드: {', '.join(api.get('error_codes', [])) or '미기록'}",
        ]
        actions = [
            "서울교통공사 API 응답 상태와 호출 제한을 확인",
            "실패 요청에 지수 백오프 재시도와 마지막 정상 데이터 캐시 적용",
            "HTTP 상태 및 timeout 유형별 알림을 분리해 장애 범위를 확인",
        ]
    elif traffic_requests >= traffic_threshold:
        status = "위험"
        severity = "critical"
        title = "접속 트래픽 급증 및 처리 용량 위험"
        summary = (
            f"최근 관측 요청량 {traffic_requests:,}건이 처리 기준 {traffic_threshold:,}건을 초과했습니다. "
            "단일 백엔드 인스턴스에서 지연과 요청 실패가 발생할 수 있습니다."
        )
        evidence = [
            f"관측 요청량 {traffic_requests:,}건 (임계치 {traffic_threshold:,}건)",
            f"최대 처리량 {traffic.get('peak_requests_per_second', 0):.0f} req/s",
            f"최대 CPU {traffic.get('peak_cpu_percent', 0):.1f}% / 최대 메모리 {traffic.get('peak_memory_percent', 0):.1f}%",
            f"최대 동시 요청 {traffic.get('peak_queue_depth', 0)}건 / 가동 인스턴스 {traffic.get('instance_count', 0)}대",
        ]
        actions = [
            "백엔드 인스턴스를 수평 확장하고 로드밸런서로 요청을 분산",
            "정적 조회 및 최근 도착 응답에 캐시를 적용해 API 부하를 감소",
            "CPU 또는 요청량 기준 자동 확장 정책을 설정하고 DB 연결 풀 한도를 점검",
        ]
        trend_label = "요청량 (건)"
        trend_points = [
            {**point, "baseline": traffic_threshold}
            for point in traffic.get("points", [])
        ] or [{"ts": now, "value": traffic_requests, "baseline": traffic_threshold}]
    elif scheduler_error > 0:
        status = "위험"
        severity = "critical"
        title = "수집 스케줄러 실행 실패"
        summary = f"최근 분석 구간에서 수집 스케줄러 오류 {scheduler_error}건이 감지되었습니다."
        evidence = [
            f"실패 작업 {scheduler_error}건 / 전체 실행 {scheduler.get('total', 0)}건",
            *scheduler.get("error_messages", []),
        ]
        actions = [
            "스케줄러 예외 로그와 외부 API 연결 상태를 확인",
            "수집 실패 구간을 재실행하고 누락된 데이터 여부를 점검",
            "반복 실패 시 스케줄러 프로세스를 재시작하고 알림을 발송",
        ]
    elif api_error_rate >= 0.05:
        status = "주의"
        severity = "warning"
        title = "API 오류 증가"
        summary = f"도착 API 오류율 {api_error_rate * 100:.1f}%가 주의 기준 5%를 초과했습니다."
        evidence = [f"오류율 {api_error_rate * 100:.1f}% (주의 기준 5%)"]
        actions = ["오류율 추이를 점검", "실패 응답 코드를 분류해 확인"]
    else:
        status = "정상"
        severity = "info"
        title = "특이 이상 없음"
        summary = "현재 구간에서 특이 이상이 감지되지 않았습니다."
        evidence = ["API 오류율과 스케줄러 오류, 트래픽 요청량이 설정된 임계치 이내입니다."]
        actions = ["현재 모니터링 상태 유지"]

    anomaly_count = 0 if severity == "info" else 1
    return {
        "overall_status": status,
        "today_anomaly_count": anomaly_count,
        "latest_anomaly": {
            "occurred_at": now,
            "title": title,
            "severity": severity,
            "summary": summary,
        },
        "insights": [
            {"title": title, "summary": summary}
        ],
        "anomalies": [
            {"severity": severity, "title": title, "occurred_at": now, "category": "fallback"}
        ],
        "selected_anomaly_detail": {
            "title": title,
            "occurred_at": now,
            "description": summary,
            "evidence": evidence,
            "recommended_actions": actions,
        },
        "metric_trend": {
            "label": trend_label,
            "points": trend_points,
        },
    }


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
