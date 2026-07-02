"""근거 있는(evidence-based) 통계 기반 이상탐지.

설계 근거 (출처):
- Google SRE, The Four Golden Signals: latency / traffic / errors / saturation
  https://sre.google/sre-book/monitoring-distributed-systems/
- 통계적 이상탐지: z-score = (현재값 - 기준선평균) / 기준선표준편차, |z|>2 이상
  (RisingWave, Tinybird 등 시계열 통계 이상탐지 관행)
- latency/traffic은 절대값이 아니라 "과거 같은 시간대 baseline 대비 배수"로 판단
  (latency ×1.5 주의 / ×2 위험, traffic 급증 ×2), errors는 절대율 OR baseline 대비 급증,
  saturation(CPU/MEM)은 절대 60/80% 기준.

핵심: 과거 baseline을 "죽은 계산"이 아니라 탐지의 중심으로 사용한다.

이 모듈은 서드파티 의존성 없이(stdlib만) 작성되어 단위 테스트가 가능하다.
출력 스키마는 관리자 대시보드가 파싱하는 subway-anomaly-results 계약과 동일하게 유지한다.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
STATUS_BY_SEVERITY = {"info": "정상", "warning": "주의", "critical": "위험"}

# baseline 통계를 계산할 필드 (rate/ratio/point 지표만 사용 → 분석 창 길이에 무관하게 비교 가능)
_GOLDEN_FIELDS = ("requests_per_second", "error_rate", "avg_elapsed_ms",
                  "p95_elapsed_ms", "cpu_percent", "memory_percent")
_METRIC_FIELDS = ("fetched_total", "line1_saved")


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def mean_std(values: list[float]) -> tuple[float, float, int]:
    """표본 평균/표준편차/표본 수. n<2면 std=0."""
    vals = [v for v in values if v is not None]
    n = len(vals)
    if n == 0:
        return 0.0, 0.0, 0
    m = sum(vals) / n
    if n < 2:
        return m, 0.0, n
    var = sum((v - m) ** 2 for v in vals) / (n - 1)
    return m, math.sqrt(var), n


def zscore(current: float, mean: float, std: float) -> float:
    if std <= 0:
        return 0.0
    return (current - mean) / std


def compute_baseline_stats(events: list[dict[str, Any]]) -> dict[str, Any]:
    """과거 같은 시간대 이벤트들에서 신호별 평균/표준편차/표본수를 계산한다."""
    buckets: dict[str, list[float]] = {}
    for field in (*_GOLDEN_FIELDS, *_METRIC_FIELDS):
        buckets[field] = []

    for event in events:
        for field in _GOLDEN_FIELDS:
            if event.get(field) is not None:
                buckets[field].append(_f(event.get(field)))
        if event.get("event_type") == "METRIC_COLLECTION":
            for field in _METRIC_FIELDS:
                if event.get(field) is not None:
                    buckets[field].append(_f(event.get(field)))

    stats: dict[str, Any] = {}
    sample_count = 0
    for field, vals in buckets.items():
        m, s, n = mean_std(vals)
        stats[field] = {"mean": m, "std": s, "count": n}
        sample_count = max(sample_count, n)
    stats["sample_count"] = sample_count
    return stats


def _config() -> dict[str, float]:
    def g(key: str, default: str) -> float:
        return float(os.getenv(key, default))

    return {
        "z_warn": g("Z_SCORE_WARN", "2.0"),
        "z_crit": g("Z_SCORE_CRIT", "3.0"),
        "lat_warn": g("LATENCY_WARN_RATIO", "1.5"),
        "lat_crit": g("LATENCY_CRIT_RATIO", "2.0"),
        "spike": g("TRAFFIC_SPIKE_RATIO", "2.0"),
        "drop": g("TRAFFIC_DROP_RATIO", "0.5"),
        "cpu_warn": g("CPU_WARN", "60"),
        "cpu_crit": g("CPU_CRIT", "80"),
        "mem_warn": g("MEM_WARN", "60"),
        "mem_crit": g("MEM_CRIT", "80"),
        "api_warn": g("API_ERROR_WARN", "0.05"),
        "api_crit": g("API_ERROR_CRIT", "0.20"),
        "coll_drop": g("COLLECTION_DROP_RATIO", "0.5"),
        "min_samples": g("MIN_BASELINE_SAMPLES", "5"),
        "traffic_threshold": g("TRAFFIC_REQUEST_THRESHOLD", "1000"),
    }


def _stat(baseline: dict[str, Any], field: str, min_samples: float):
    """baseline이 통계적으로 쓸 만하면 (mean, std)를, 아니면 None을 반환한다."""
    s = baseline.get(field) if baseline else None
    if not s:
        return None
    if s.get("count", 0) < min_samples or s.get("std", 0.0) <= 0:
        return None
    return s.get("mean", 0.0), s.get("std", 0.0)


def _worst(severity_a: str, severity_b: str) -> str:
    return severity_a if SEVERITY_ORDER[severity_a] >= SEVERITY_ORDER[severity_b] else severity_b


def evaluate(metrics: dict[str, Any], baseline: dict[str, Any], off_hours: bool,
             now_iso: str | None = None) -> dict[str, Any]:
    """근거 있는 이상탐지 평가. 대시보드 계약과 동일한 결과 dict를 반환한다."""
    cfg = _config()
    now = now_iso or datetime.now(timezone.utc).isoformat()
    api = metrics.get("api", {}) or {}
    traffic = metrics.get("traffic", {}) or {}
    scheduler = metrics.get("scheduler", {}) or {}
    collection = metrics.get("collection", {}) or {}
    min_samples = cfg["min_samples"]

    # (priority, severity, title, summary, evidence[], actions[], trend)
    signals: list[dict[str, Any]] = []

    def add(priority, severity, title, summary, evidence, actions, trend):
        signals.append({
            "priority": priority, "severity": severity, "title": title,
            "summary": summary, "evidence": evidence, "actions": actions, "trend": trend,
        })

    # 1) 외부 API 오류 (절대 임계값 + baseline 상대 급증). 운영 종료 시간엔 수집이 멈추므로 제외.
    if not off_hours:
        _eval_api_errors(api, cfg, now, add)

    # 2) 시스템 포화 saturation (CPU/MEM 절대 기준). 상시 평가.
    _eval_saturation(traffic, cfg, now, add)

    # 3) 응답시간 latency (baseline 배수). 운영 종료 시간엔 트래픽이 낮아 의미가 적어 제외.
    if not off_hours:
        _eval_latency(traffic, baseline, cfg, min_samples, now, add)

    # 4) 트래픽 traffic (baseline 대비 급증/급감 + 절대 요청량 가드레일). 상시 평가.
    _eval_traffic(traffic, baseline, cfg, min_samples, now, add)

    # 5) 스케줄러 실패 (절대). 운영 종료 시간엔 스케줄러가 멈추므로 제외.
    if not off_hours:
        _eval_scheduler(scheduler, now, add)

    # 6) 수집량 급감 collection drop (baseline 대비). 운영 종료 시간엔 제외.
    if not off_hours:
        _eval_collection(collection, baseline, cfg, min_samples, now, add)

    anomalies = [s for s in signals if s["severity"] != "info"]
    return _build_result(anomalies, baseline, off_hours, now, cfg)


def _eval_api_errors(api, cfg, now, add):
    total = _f(api.get("total"))
    if total <= 0:
        return
    rate = _f(api.get("error_rate"))
    if rate < cfg["api_warn"]:
        return
    severity = "critical" if rate >= cfg["api_crit"] else "warning"
    threshold = cfg["api_crit"] if severity == "critical" else cfg["api_warn"]
    evidence = [
        f"오류율 {rate * 100:.1f}% (임계치 {threshold * 100:.0f}%)",
        f"도착 API 요청 {int(total)}건 중 {int(_f(api.get('error')))}건 실패",
        f"평균 응답 {_f(api.get('avg_elapsed_ms')):.0f}ms / 최대 {_f(api.get('max_elapsed_ms')):.0f}ms",
        f"응답 코드: {', '.join(api.get('http_statuses', [])) or '미기록'} / "
        f"원인 코드: {', '.join(api.get('error_codes', [])) or '미기록'}",
    ]
    actions = [
        "서울교통공사 API 응답 상태와 호출 제한을 확인",
        "실패 요청에 지수 백오프 재시도와 마지막 정상 데이터 캐시 적용",
        "HTTP 상태/timeout 유형별로 장애 범위를 확인",
    ]
    add(1, severity, "서울 실시간 도착 API 응답 장애" if severity == "critical" else "API 오류 증가",
        f"도착 API 오류율 {rate * 100:.1f}%가 임계치 {threshold * 100:.0f}%를 초과했습니다.",
        evidence, actions,
        {"label": "API 오류율 (%)", "points": [{"ts": now, "value": round(rate * 100, 2),
                                              "baseline": round(cfg["api_crit"] * 100, 2)}]})


def _eval_saturation(traffic, cfg, now, add):
    cpu = _f(traffic.get("peak_cpu_percent"))
    mem = _f(traffic.get("peak_memory_percent"))
    worst_val = max(cpu, mem)
    if worst_val < cfg["cpu_warn"]:
        return
    severity = "critical" if worst_val >= cfg["cpu_crit"] else "warning"
    threshold = cfg["cpu_crit"] if severity == "critical" else cfg["cpu_warn"]
    evidence = [
        f"최대 CPU {cpu:.1f}% / 최대 메모리 {mem:.1f}% (임계 {threshold:.0f}%)",
        f"최대 동시 요청 {int(_f(traffic.get('peak_queue_depth')))}건 / "
        f"가동 인스턴스 {int(_f(traffic.get('instance_count')))}대",
    ]
    actions = [
        "백엔드 인스턴스를 수평 확장하고 로드밸런서로 요청을 분산",
        "CPU/메모리 기준 자동 확장 정책을 설정",
        "GC/힙 사용량과 스레드풀 포화 여부를 점검",
    ]
    add(2, severity, "시스템 자원 포화",
        f"자원 사용률이 {worst_val:.1f}%로 포화 임계치 {threshold:.0f}%를 초과했습니다.",
        evidence, actions,
        {"label": "자원 사용률 (%)", "points": [{"ts": now, "value": round(worst_val, 1),
                                             "baseline": round(cfg["cpu_crit"], 1)}]})


def _eval_latency(traffic, baseline, cfg, min_samples, now, add):
    # p95가 있으면 p95, 없으면 avg로 폴백
    use_p95 = _f(traffic.get("p95_elapsed_ms")) > 0
    current = _f(traffic.get("p95_elapsed_ms")) if use_p95 else _f(traffic.get("avg_elapsed_ms"))
    if current <= 0:
        return
    field = "p95_elapsed_ms" if use_p95 else "avg_elapsed_ms"
    stat = _stat(baseline, field, min_samples)
    if stat is None and not use_p95:
        stat = _stat(baseline, "avg_elapsed_ms", min_samples)
    if stat is None:
        return  # baseline이 없으면 latency 절대판단은 하지 않음(근거 부족)
    mean, std = stat
    if mean <= 0:
        return
    ratio = current / mean
    z = zscore(current, mean, std)
    if ratio < cfg["lat_warn"]:
        return
    severity = "critical" if ratio >= cfg["lat_crit"] else "warning"
    label = "p95 응답시간" if use_p95 else "평균 응답시간"
    evidence = [
        f"{label} {current:.0f}ms = 기준선({mean:.0f}±{std:.0f}ms) 대비 {ratio:.1f}배 (z={z:.1f})",
        f"기준선 표본 {int(baseline.get(field, {}).get('count', 0))}건 (같은 시간대 과거)",
    ]
    actions = [
        "느린 엔드포인트와 외부 API 응답시간을 분리해 확인",
        "DB 커넥션 풀/슬로우 쿼리를 점검",
        "캐시 적용 및 타임아웃/서킷브레이커 검토",
    ]
    add(3, severity, "응답시간 급증",
        f"{label}이 과거 같은 시간대 기준선의 {ratio:.1f}배(z={z:.1f})로 상승했습니다.",
        evidence, actions,
        {"label": f"{label} (ms)", "points": [{"ts": now, "value": round(current, 0),
                                             "baseline": round(mean, 0)}]})


def _eval_traffic(traffic, baseline, cfg, min_samples, now, add):
    peak_rps = _f(traffic.get("peak_requests_per_second"))
    request_count = _f(traffic.get("request_count"))
    stat = _stat(baseline, "requests_per_second", min_samples)

    # (a) baseline 대비 급증 (근거 있는 상대 판단)
    if stat is not None and peak_rps > 0:
        mean, std = stat
        if mean > 0:
            ratio = peak_rps / mean
            z = zscore(peak_rps, mean, std)
            if ratio >= cfg["spike"]:
                severity = "critical" if (ratio >= cfg["spike"] * 1.5 or z >= cfg["z_crit"]) else "warning"
                evidence = [
                    f"최대 {peak_rps:.1f} req/s = 기준선({mean:.1f}±{std:.1f}) 대비 {ratio:.1f}배 (z={z:.1f})",
                    f"관측 요청량 {int(request_count):,}건",
                    f"최대 CPU {_f(traffic.get('peak_cpu_percent')):.1f}% / "
                    f"메모리 {_f(traffic.get('peak_memory_percent')):.1f}%",
                ]
                add(4, severity, "접속 트래픽 급증",
                    f"요청량이 과거 같은 시간대 기준선의 {ratio:.1f}배(z={z:.1f})로 급증했습니다.",
                    evidence,
                    ["백엔드 수평 확장 및 로드밸런싱", "응답 캐시 적용으로 부하 완화",
                     "자동 확장 정책과 DB 커넥션 풀 한도 점검"],
                    {"label": "요청량 (req/s)", "points": [{"ts": now, "value": round(peak_rps, 1),
                                                         "baseline": round(mean, 1)}]})
                return

    # (b) 절대 요청량 가드레일 (baseline이 없거나 급증 미검출 시)
    if request_count >= cfg["traffic_threshold"]:
        points = [{**p, "baseline": cfg["traffic_threshold"]} for p in traffic.get("points", [])] \
            or [{"ts": now, "value": request_count, "baseline": cfg["traffic_threshold"]}]
        add(4, "critical", "접속 트래픽 급증 및 처리 용량 위험",
            f"관측 요청량 {int(request_count):,}건이 처리 기준 {int(cfg['traffic_threshold']):,}건을 초과했습니다.",
            [f"관측 요청량 {int(request_count):,}건 (임계치 {int(cfg['traffic_threshold']):,}건)",
             f"최대 {peak_rps:.1f} req/s"],
            ["백엔드 수평 확장 및 로드밸런싱", "응답 캐시 적용", "자동 확장 정책 설정"],
            {"label": "요청량 (건)", "points": points})


def _eval_scheduler(scheduler, now, add):
    error = _f(scheduler.get("error"))
    if error <= 0:
        return
    evidence = [f"실패 작업 {int(error)}건 / 전체 실행 {int(_f(scheduler.get('total')))}건",
                *scheduler.get("error_messages", [])]
    add(5, "critical", "수집 스케줄러 실행 실패",
        f"최근 분석 구간에서 수집 스케줄러 오류 {int(error)}건이 감지되었습니다.",
        evidence,
        ["스케줄러 예외 로그와 외부 API 연결 상태를 확인",
         "수집 실패 구간을 재실행하고 누락 데이터를 점검",
         "반복 실패 시 스케줄러 프로세스를 재시작"],
        {"label": "스케줄러 실패 (건)", "points": [{"ts": now, "value": error, "baseline": 0}]})


def _eval_collection(collection, baseline, cfg, min_samples, now, add):
    current = _f(collection.get("fetched_total"))
    stat = _stat(baseline, "fetched_total", min_samples)
    if stat is None or current <= 0:
        return
    mean, std = stat
    if mean <= 0:
        return
    ratio = current / mean
    if ratio > cfg["coll_drop"]:
        return
    z = zscore(current, mean, std)
    add(6, "warning", "도착정보 수집량 급감",
        f"수집 건수가 과거 같은 시간대 기준선의 {ratio:.0%} 수준으로 감소했습니다.",
        [f"수집 {int(current)}건 = 기준선({mean:.0f}±{std:.0f}건) 대비 {ratio:.0%} (z={z:.1f})",
         "외부 API 부분 실패 또는 수집 누락 가능성"],
        ["외부 API 응답 완전성 확인", "페이지별 수집 성공 여부 점검", "누락 구간 재수집"],
        {"label": "수집 건수", "points": [{"ts": now, "value": round(current, 0),
                                       "baseline": round(mean, 0)}]})


def _build_result(anomalies, baseline, off_hours, now, cfg):
    sample_count = int(baseline.get("sample_count", 0)) if baseline else 0
    baseline_note = (f"기준선 표본 {sample_count}건 기반 통계 비교"
                     if sample_count >= cfg["min_samples"]
                     else f"기준선 표본 부족(n={sample_count}) — 절대 임계값 위주 판단")

    if not anomalies:
        if off_hours:
            summary = "심야 운영 종료 시간대로, 트래픽/포화만 분석했으며 특이 이상이 없습니다."
            evidence = ["운영 종료 시간대(수집 중단)에는 API/스케줄러/수집 지표를 평가하지 않습니다.", baseline_note]
        else:
            summary = "현재 구간에서 특이 이상이 감지되지 않았습니다."
            evidence = ["모든 golden signal(오류/지연/트래픽/포화)이 기준선·임계치 이내입니다.", baseline_note]
        return {
            "overall_status": "정상",
            "today_anomaly_count": 0,
            "latest_anomaly": {"occurred_at": now, "title": "특이 이상 없음",
                               "severity": "info", "summary": summary},
            "insights": [{"title": "특이 이상 없음", "summary": summary}],
            "anomalies": [{"severity": "info", "title": "특이 이상 없음",
                           "occurred_at": now, "category": "normal"}],
            "selected_anomaly_detail": {"title": "특이 이상 없음", "occurred_at": now,
                                        "description": summary, "evidence": evidence,
                                        "recommended_actions": ["현재 모니터링 상태 유지"]},
            "metric_trend": {"label": "이상 신호 수", "points": [{"ts": now, "value": 0, "baseline": 0}]},
        }

    # 심각도 → 우선순위 순으로 정렬, 대표(primary) 선정
    anomalies.sort(key=lambda s: (-SEVERITY_ORDER[s["severity"]], s["priority"]))
    primary = anomalies[0]
    overall = "info"
    for s in anomalies:
        overall = _worst(overall, s["severity"])

    return {
        "overall_status": STATUS_BY_SEVERITY[overall],
        "today_anomaly_count": len(anomalies),
        "latest_anomaly": {"occurred_at": now, "title": primary["title"],
                           "severity": primary["severity"], "summary": primary["summary"]},
        "insights": [{"title": s["title"], "summary": s["summary"]} for s in anomalies],
        "anomalies": [{"severity": s["severity"], "title": s["title"],
                       "occurred_at": now, "category": "golden_signal"} for s in anomalies],
        "selected_anomaly_detail": {
            "title": primary["title"],
            "occurred_at": now,
            "description": primary["summary"],
            "evidence": [*primary["evidence"], baseline_note],
            "recommended_actions": primary["actions"],
        },
        "metric_trend": primary["trend"],
    }
