#!/usr/bin/env python3
"""진단 에이전트 평가 케이스 생성기.

로그 이벤트(events)가 길어 손으로 jsonl을 쓰기 어렵다. 여기서 현실적인 로그를
합성해 cases_diagnosis.jsonl로 고정한다(재현·수정 용이). 생성된 jsonl이 정본이고,
run_diagnosis.py는 그 jsonl만 읽는다.

케이스는 실제 detection/agent가 만드는 event_type/필드 형태를 따른다.
정답(expected)은 구현을 보지 않고 도메인 규칙으로 정했다.

실행: python evals/gen_diagnosis_cases.py  → cases_diagnosis.jsonl 생성
"""
import json
import pathlib

OUT = pathlib.Path(__file__).parent / "cases_diagnosis.jsonl"


def api(ts, ok, status="200", code=None, endpoint="/arrival/page1", msg=None):
    e = {"@timestamp": ts, "event_type": "API_COLLECTION",
         "success": "true" if ok else "false", "http_status": status, "endpoint": endpoint}
    if code:
        e["error_code"] = code
    if msg:
        e["error_msg"] = msg
    return e


def sched(ts, ok, code=None, msg=None):
    e = {"@timestamp": ts, "event_type": "SCHEDULER", "scheduler_name": "fetchAndSaveArrivalInfo",
         "success": "true" if ok else "false"}
    if code:
        e["error_code"] = code
    if msg:
        e["error_msg"] = msg
    return e


def traffic(ts, endpoint, rps, cpu=30):
    return {"@timestamp": ts, "event_type": "TRAFFIC", "endpoint": endpoint,
            "requests_per_second": str(rps), "cpu_percent": str(cpu)}


def anomaly(title, severity, keys, evidence):
    return {"overall_status": "위험" if severity == "critical" else "주의",
            "detected_keys": keys,
            "latest_anomaly": {"title": title, "severity": severity, "summary": evidence[0]},
            "selected_anomaly_detail": {"evidence": evidence}}


CASES = []


def add(cid, category, label, events, anom, metrics, expected):
    CASES.append({"id": cid, "category": category, "label": label,
                  "input": {"anomaly": anom, "metrics": metrics, "events": events},
                  "expected": expected})


# 1. 504 타임아웃이 특정 엔드포인트에 집중 — 원인 명확
ev = [api(f"2026-07-22T08:0{i}:00Z", True) for i in range(7)]
ev += [api(f"2026-07-22T08:15:{i:02d}Z", False, "504", "UPSTREAM_TIMEOUT", "/arrival/page3",
           "read timed out") for i in range(9)]
add("api_page3_timeout", "resolved", "504 타임아웃이 /arrival/page3에 08:15부터 집중", ev,
    anomaly("서울 실시간 도착 API 응답 장애", "critical", ["api_errors"],
            ["오류율 56% (임계 20%)", "16건 중 9건 실패"]),
    {"api": {"total": 16, "error": 9, "error_rate": 0.56}, "traffic": {}},
    {"resolution": "완료", "cause_elements": ["page3", "타임아웃/504/UPSTREAM_TIMEOUT"],
     "cause_summary": "/arrival/page3 엔드포인트에서 외부 API 타임아웃(504)이 08:15부터 집중 발생"})

# 2. 429 호출 한도가 특정 시각 폭증 — 원인 명확
ev = [api(f"2026-07-22T09:0{i}:00Z", True) for i in range(6)]
ev += [api(f"2026-07-22T09:12:{i:02d}Z", False, "429", "RATE_LIMITED", "/arrival/page2",
           "call limit exceeded") for i in range(8)]
add("api_rate_limited", "resolved", "429 호출 한도가 09:12에 폭증", ev,
    anomaly("서울 실시간 도착 API 응답 장애", "critical", ["api_errors"],
            ["오류율 57% (임계 20%)", "14건 중 8건 실패"]),
    {"api": {"total": 14, "error": 8, "error_rate": 0.57}, "traffic": {}},
    {"resolution": "완료", "cause_elements": ["429/한도/RATE_LIMITED", "09:12/시간대 집중"],
     "cause_summary": "호출 한도 초과(429)가 09:12에 집중 발생, API 쿼터 소진"})

# 3. 스케줄러 실패가 특정 예외로 반복 — 원인 명확
ev = [sched(f"2026-07-22T10:0{i}:00Z", True) for i in range(4)]
ev += [sched(f"2026-07-22T10:1{i}:00Z", False, "ConnectException",
             "서울 API 연결 타임아웃") for i in range(3)]
add("scheduler_connection_fail", "resolved", "스케줄러가 ConnectException으로 3회 반복 실패", ev,
    anomaly("수집 스케줄러 실행 실패", "critical", ["scheduler"],
            ["실패 작업 3건 / 전체 7건", "서울 API 연결 타임아웃"]),
    {"api": {}, "traffic": {}, "scheduler": {"total": 7, "error": 3}},
    {"resolution": "완료", "cause_elements": ["연결/ConnectException/타임아웃", "스케줄러/수집"],
     "cause_summary": "외부 API 연결 실패(ConnectException)로 수집 스케줄러가 반복 중단"})

# 4. 한 엔드포인트만 500 — 원인 명확
ev = [api(f"2026-07-22T11:0{i}:00Z", True, endpoint="/arrival/page1") for i in range(8)]
ev += [api(f"2026-07-22T11:1{i}:00Z", False, "500", "INTERNAL_ERROR", "/favorites",
           "null reference") for i in range(5)]
add("single_endpoint_500", "resolved", "/favorites 엔드포인트만 500 발생", ev,
    anomaly("API 오류 증가", "warning", ["api_errors"],
            ["오류율 38% (임계 5%)", "13건 중 5건 실패"]),
    {"api": {"total": 13, "error": 5, "error_rate": 0.38}, "traffic": {}},
    {"resolution": "완료", "cause_elements": ["/favorites", "500/INTERNAL_ERROR"],
     "cause_summary": "/favorites 엔드포인트에서만 500 내부 오류 발생, 특정 기능 결함"})

# 5. 두 원인 공존(504 page3 + 429 page1) — 완료 기대(주요인 식별)
ev = [api(f"2026-07-22T12:0{i}:00Z", True) for i in range(5)]
ev += [api(f"2026-07-22T12:1{i}:00Z", False, "504", "UPSTREAM_TIMEOUT", "/arrival/page3",
           "timeout") for i in range(6)]
ev += [api(f"2026-07-22T12:2{i}:00Z", False, "429", "RATE_LIMITED", "/arrival/page1",
           "rate") for i in range(2)]
add("mixed_two_causes", "resolved", "504(page3)와 429(page1) 두 원인 공존", ev,
    anomaly("서울 실시간 도착 API 응답 장애", "critical", ["api_errors"],
            ["오류율 62% (임계 20%)", "13건 중 8건 실패"]),
    {"api": {"total": 13, "error": 8, "error_rate": 0.62}, "traffic": {}},
    {"resolution": "완료", "cause_elements": ["504/타임아웃", "page3"],
     "cause_summary": "주요인은 page3의 504 타임아웃(6건), 부수적으로 page1 429(2건)"})

# 6. 오류가 여러 endpoint/code에 골고루 분산 — 원인 불명확(미결 기대)
ev = [api(f"2026-07-22T13:0{i}:00Z", True) for i in range(5)]
codes = [("500", "INTERNAL_ERROR", "/a"), ("503", "UNAVAILABLE", "/b"),
         ("504", "TIMEOUT", "/c"), ("429", "RATE", "/d"), ("502", "BAD_GATEWAY", "/e")]
ev += [api(f"2026-07-22T13:1{i}:00Z", False, c[0], c[1], c[2]) for i, c in enumerate(codes)]
add("diffuse_errors", "unresolved", "오류가 여러 endpoint/code에 골고루 분산", ev,
    anomaly("API 오류 증가", "warning", ["api_errors"],
            ["오류율 50% (임계 5%)", "10건 중 5건 실패"]),
    {"api": {"total": 10, "error": 5, "error_rate": 0.50}, "traffic": {}},
    {"resolution": "미결", "cause_elements": [],
     "cause_summary": "특정 패턴 없이 여러 코드/엔드포인트에 분산 — 단일 근본원인 특정 불가"})

# 7. 로그가 극히 적음(총 4건) — 판단 근거 부족(미결 기대)
ev = [api("2026-07-22T14:00:00Z", True),
      api("2026-07-22T14:01:00Z", False, "500", "INTERNAL_ERROR", "/x"),
      api("2026-07-22T14:02:00Z", True),
      api("2026-07-22T14:03:00Z", False, "500", "INTERNAL_ERROR", "/x")]
add("sparse_logs", "unresolved", "로그 총 4건, 판단 근거 부족", ev,
    anomaly("API 오류 증가", "warning", ["api_errors"],
            ["오류율 50% (임계 5%)", "4건 중 2건 실패", "총 호출량 극소"]),
    {"api": {"total": 4, "error": 2, "error_rate": 0.50}, "traffic": {}},
    {"resolution": "미결", "cause_elements": [],
     "cause_summary": "로그 표본이 너무 적어 근본원인을 신뢰성 있게 특정할 수 없음"})

# 8. 트래픽 급증에 동반한 CPU 포화 — 원인 명확(트래픽 유발)
ev = [traffic(f"2026-07-22T15:0{i}:00Z", "/stations/arrivals/all", 3, 25) for i in range(5)]
ev += [traffic(f"2026-07-22T15:1{i}:00Z", "/stations/arrivals/all", 55 + i, 88 + i)
       for i in range(4)]
add("saturation_traffic_driven", "resolved", "트래픽 급증과 동반한 CPU 포화", ev,
    anomaly("시스템 자원 포화", "critical", ["saturation", "traffic"],
            ["최대 CPU 91% (임계 80%)", "요청량 55→58 req/s로 급증"]),
    {"api": {}, "traffic": {"instance_count": 1, "peak_cpu_percent": 91,
                            "peak_requests_per_second": 58}},
    {"resolution": "완료", "cause_elements": ["트래픽/요청 급증", "CPU/포화"],
     "cause_summary": "/stations/arrivals/all로의 트래픽 급증(3→58 req/s)이 CPU 포화를 유발"})

OUT.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in CASES),
               encoding="utf-8")
print(f"생성: {OUT} ({len(CASES)} 케이스)")
from collections import Counter
print("범주:", dict(Counter(c["category"] for c in CASES)))
