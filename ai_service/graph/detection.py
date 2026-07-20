"""근거 있는(evidence-based) 통계 기반 이상탐지.

설계 근거 (출처):
- Google SRE, The Four Golden Signals: latency / traffic / errors / saturation
  https://sre.google/sre-book/monitoring-distributed-systems/
- 통계적 이상탐지: z-score = (현재값 - 기준선평균) / 기준선표준편차

비교 규칙 (핵심):
- **평균은 평균끼리, 피크는 피크끼리 비교한다.**
  창 내 최댓값(max of N)을 1분 표본의 평균과 비교하면 E[max of N] > mean 이므로
  정상 상태에서도 배수 임계를 상시 초과한다(구조적 거짓양성).
  따라서 두 축으로 나눈다:
    (a) 창 평균 vs 기준선 평균  → 배수 + z-score 이중 게이트
    (b) 창 피크 vs 기준선 p99   → 꼬리 대 꼬리(tail-vs-tail) 비교
- z-score는 문서상 장식이 아니라 실제 게이트다. 배수 조건과 z 조건을 **모두**
  만족해야 이상으로 판정한다(다중 신호에서의 거짓양성 억제).
- 절대 가드레일은 총 요청수(창 길이 의존)가 아니라 **req/s**로 판단한다.
- 플래핑 방지를 위해 연속 N회 감지된 신호만 확정(confirmed)으로 승격한다.

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


def percentile(values: list[float], q: float) -> float:
    """선형 보간 백분위수(numpy 없이). q는 0.0~1.0."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return float(vals[0])
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return float(vals[int(pos)])
    return float(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo))


def zscore(current: float, mean: float, std: float) -> float:
    if std <= 0:
        return 0.0
    return (current - mean) / std


def compute_baseline_stats(events: list[dict[str, Any]]) -> dict[str, Any]:
    """과거 같은 시간대 이벤트들에서 신호별 평균/표준편차/분위수/표본수를 계산한다.

    p95/p99를 함께 계산하는 이유: 현재 창의 '피크'는 기준선의 '평균'이 아니라
    기준선의 '상위 분위수'와 비교해야 통계적으로 같은 대상끼리의 비교가 된다.
    """
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
        stats[field] = {
            "mean": m,
            "std": s,
            "count": n,
            "p95": percentile(vals, 0.95),
            "p99": percentile(vals, 0.99),
        }
        sample_count = max(sample_count, n)
    stats["sample_count"] = sample_count
    return stats


def count_api_instances(golden_events: list[dict[str, Any]]) -> int:
    """가동 중인 **API 인스턴스** 수. 자동 확장 판단의 입력이므로 정확해야 한다.

    두 가지를 걸러내야 한다:
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
    return int(max((_f(e.get("instance_count")) for e in api_events), default=0.0))


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
        # 절대 가드레일은 창 길이에 의존하는 총 요청수가 아니라 req/s로 판단한다.
        "rps_warn": g("TRAFFIC_RPS_WARN", "20"),
        "rps_crit": g("TRAFFIC_RPS_CRIT", "50"),
        # 플래핑 방지: 연속 N회 감지되어야 확정 알람으로 승격
        "consecutive_n": g("ANOMALY_CONSECUTIVE_N", "2"),
    }


def _stat(baseline: dict[str, Any], field: str, min_samples: float):
    """baseline이 통계적으로 쓸 만하면 (mean, std)를, 아니면 None을 반환한다."""
    s = baseline.get(field) if baseline else None
    if not s:
        return None
    if s.get("count", 0) < min_samples or s.get("std", 0.0) <= 0:
        return None
    return s.get("mean", 0.0), s.get("std", 0.0)


def _quantile(baseline: dict[str, Any], field: str, key: str, min_samples: float):
    """기준선의 상위 분위수(p95/p99). 표본이 부족하면 None."""
    s = baseline.get(field) if baseline else None
    if not s or s.get("count", 0) < min_samples:
        return None
    val = _f(s.get(key))
    return val if val > 0 else None


def _worst(severity_a: str, severity_b: str) -> str:
    return severity_a if SEVERITY_ORDER[severity_a] >= SEVERITY_ORDER[severity_b] else severity_b


def evaluate(metrics: dict[str, Any], baseline: dict[str, Any], off_hours: bool,
             now_iso: str | None = None,
             recent_keys: list[list[str]] | None = None) -> dict[str, Any]:
    """근거 있는 이상탐지 평가. 대시보드 계약과 동일한 결과 dict를 반환한다.

    recent_keys: 직전 실행들의 감지 신호 key 목록(최신순). 디바운스 판정에 사용한다.
    """
    cfg = _config()
    now = now_iso or datetime.now(timezone.utc).isoformat()
    api = metrics.get("api", {}) or {}
    traffic = metrics.get("traffic", {}) or {}
    scheduler = metrics.get("scheduler", {}) or {}
    collection = metrics.get("collection", {}) or {}
    min_samples = cfg["min_samples"]

    # (key, priority, severity, title, summary, evidence[], actions[], trend)
    signals: list[dict[str, Any]] = []

    def add(key, priority, severity, title, summary, evidence, actions, trend):
        signals.append({
            "key": key, "priority": priority, "severity": severity, "title": title,
            "summary": summary, "evidence": evidence, "actions": actions, "trend": trend,
        })

    # 1) 외부 API 오류 (절대 임계값). 운영 종료 시간엔 수집이 멈추므로 제외.
    if not off_hours:
        _eval_api_errors(api, cfg, now, add)

    # 2) 시스템 포화 saturation (CPU/MEM 절대 기준). 상시 평가.
    _eval_saturation(traffic, cfg, now, add)

    # 3) 응답시간 latency (기준선 배수 + z 게이트). 운영 종료 시간엔 제외.
    if not off_hours:
        _eval_latency(traffic, baseline, cfg, min_samples, now, add)

    # 4) 트래픽 traffic (기준선 급증 + rps 절대 가드레일). 상시 평가.
    _eval_traffic(traffic, baseline, cfg, min_samples, now, add)

    # 5) 스케줄러 실패 (절대). 운영 종료 시간엔 스케줄러가 멈추므로 제외.
    if not off_hours:
        _eval_scheduler(scheduler, now, add)

    # 6) 수집량 급감 collection drop (기준선 대비). 운영 종료 시간엔 제외.
    if not off_hours:
        _eval_collection(collection, baseline, cfg, min_samples, now, add)

    detected = [s for s in signals if s["severity"] != "info"]
    detected_keys = [s["key"] for s in detected]
    confirmed, pending = _apply_debounce(detected, recent_keys, cfg)
    return _build_result(confirmed, pending, detected_keys, baseline, off_hours, now, cfg)


def _apply_debounce(detected, recent_keys, cfg):
    """연속 N회 감지된 신호만 확정(confirmed)으로 승격한다.

    5분 주기로 상시 관측하면 단발성 스파이크가 그대로 알람이 되어 플래핑이 발생한다.
    직전 (N-1)회 실행에서도 같은 신호가 감지되었을 때만 확정으로 본다.
    """
    need = int(cfg["consecutive_n"])
    if need <= 1 or not detected:
        return detected, []

    history = list(recent_keys or [])[: need - 1]
    # 이력이 아직 쌓이지 않았으면(콜드스타트) 억제하지 않는다 — 첫 관측을 놓치지 않기 위해.
    if len(history) < need - 1:
        return detected, []

    confirmed, pending = [], []
    for signal in detected:
        if all(signal["key"] in (keys or []) for keys in history):
            confirmed.append(signal)
        else:
            pending.append(signal)
    return confirmed, pending


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
    add("api_errors", 1, severity,
        "서울 실시간 도착 API 응답 장애" if severity == "critical" else "API 오류 증가",
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
    add("saturation", 2, severity, "시스템 자원 포화",
        f"자원 사용률이 {worst_val:.1f}%로 포화 임계치 {threshold:.0f}%를 초과했습니다.",
        evidence, actions,
        {"label": "자원 사용률 (%)", "points": [{"ts": now, "value": round(worst_val, 1),
                                             "baseline": round(cfg["cpu_crit"], 1)}]})


def _eval_latency(traffic, baseline, cfg, min_samples, now, add):
    """창 평균 vs 기준선 평균(배수 + z 이중 게이트), 창 피크 vs 기준선 p99(꼬리 비교)."""
    # p95 기준선이 쓸 만하면 p95, 아니면 avg로 폴백한다.
    field = "p95_elapsed_ms" if _f(traffic.get("p95_elapsed_ms")) > 0 else "avg_elapsed_ms"
    stat = _stat(baseline, field, min_samples)
    if stat is None and field == "p95_elapsed_ms":
        field, stat = "avg_elapsed_ms", _stat(baseline, "avg_elapsed_ms", min_samples)
    if stat is None:
        return  # baseline이 없으면 latency 절대판단은 하지 않음(근거 부족)

    use_p95 = field == "p95_elapsed_ms"
    current = _f(traffic.get(field))          # 창 '평균' (peak 아님 — 비교 대상과 통계량을 일치시킨다)
    peak = _f(traffic.get("peak_p95_elapsed_ms" if use_p95 else "peak_elapsed_ms"))
    if current <= 0:
        return
    mean, std = stat
    if mean <= 0:
        return

    ratio = current / mean
    z = zscore(current, mean, std)
    # 배수와 z를 모두 만족해야 이상으로 본다.
    if ratio < cfg["lat_warn"] or z < cfg["z_warn"]:
        return
    severity = "critical" if (ratio >= cfg["lat_crit"] and z >= cfg["z_crit"]) else "warning"

    label = "p95 응답시간" if use_p95 else "평균 응답시간"
    evidence = [
        f"{label}(창 평균) {current:.0f}ms = 기준선({mean:.0f}±{std:.0f}ms) 대비 "
        f"{ratio:.1f}배, z={z:.1f} (게이트 {cfg['lat_warn']:.1f}배 & z≥{cfg['z_warn']:.1f})",
        f"기준선 표본 {int(baseline.get(field, {}).get('count', 0))}건 (같은 시간대 과거)",
    ]
    # 꼬리 대 꼬리 비교: 창 피크가 기준선 p99를 넘으면 위험으로 승격한다.
    p99 = _quantile(baseline, field, "p99", min_samples)
    if p99 and peak > 0:
        evidence.append(f"창 최대 {peak:.0f}ms vs 기준선 p99 {p99:.0f}ms")
        if peak > p99 and severity == "warning":
            severity = "critical"
    actions = [
        "느린 엔드포인트와 외부 API 응답시간을 분리해 확인",
        "DB 커넥션 풀/슬로우 쿼리를 점검",
        "캐시 적용 및 타임아웃/서킷브레이커 검토",
    ]
    add("latency", 3, severity, "응답시간 급증",
        f"{label}이 과거 같은 시간대 기준선의 {ratio:.1f}배(z={z:.1f})로 상승했습니다.",
        evidence, actions,
        {"label": f"{label} (ms)", "points": [{"ts": now, "value": round(current, 0),
                                             "baseline": round(mean, 0)}]})


def _eval_traffic(traffic, baseline, cfg, min_samples, now, add):
    """창 평균 rps vs 기준선 평균(배수 + z), 창 피크 rps vs 기준선 p99. 폴백은 절대 rps."""
    mean_rps = _f(traffic.get("requests_per_second"))       # 창 평균
    peak_rps = _f(traffic.get("peak_requests_per_second"))  # 창 피크
    request_count = _f(traffic.get("request_count"))
    stat = _stat(baseline, "requests_per_second", min_samples)

    # (a) baseline 대비 급증 (근거 있는 상대 판단)
    if stat is not None and mean_rps > 0:
        mean, std = stat
        if mean > 0:
            ratio = mean_rps / mean
            z = zscore(mean_rps, mean, std)
            if ratio >= cfg["spike"] and z >= cfg["z_warn"]:
                severity = ("critical"
                            if (ratio >= cfg["spike"] * 1.5 and z >= cfg["z_crit"])
                            else "warning")
                evidence = [
                    f"평균 {mean_rps:.1f} req/s = 기준선({mean:.1f}±{std:.1f}) 대비 "
                    f"{ratio:.1f}배, z={z:.1f} (게이트 {cfg['spike']:.1f}배 & z≥{cfg['z_warn']:.1f})",
                    f"관측 요청량 {int(request_count):,}건 / 최대 {peak_rps:.1f} req/s (인스턴스당)",
                    f"가동 인스턴스 {int(_f(traffic.get('instance_count'))) or 1}대",
                    f"최대 CPU {_f(traffic.get('peak_cpu_percent')):.1f}% / "
                    f"메모리 {_f(traffic.get('peak_memory_percent')):.1f}%",
                ]
                p99 = _quantile(baseline, "requests_per_second", "p99", min_samples)
                if p99 and peak_rps > 0:
                    evidence.append(f"창 최대 {peak_rps:.1f} req/s vs 기준선 p99 {p99:.1f} req/s")
                    if peak_rps > p99 and severity == "warning":
                        severity = "critical"
                add("traffic", 4, severity, "접속 트래픽 급증",
                    f"요청량이 과거 같은 시간대 기준선의 {ratio:.1f}배(z={z:.1f})로 급증했습니다.",
                    evidence,
                    ["백엔드 수평 확장 및 로드밸런싱", "응답 캐시 적용으로 부하 완화",
                     "자동 확장 정책과 DB 커넥션 풀 한도 점검"],
                    {"label": "요청량 (req/s)", "points": [{"ts": now, "value": round(mean_rps, 1),
                                                         "baseline": round(mean, 1)}]})
                return

    # (b) 절대 가드레일: req/s 기준 (baseline이 없거나 급증 미검출 시)
    if peak_rps >= cfg["rps_warn"]:
        severity = "critical" if peak_rps >= cfg["rps_crit"] else "warning"
        threshold = cfg["rps_crit"] if severity == "critical" else cfg["rps_warn"]
        points = [{**p, "baseline": threshold} for p in traffic.get("points", [])] \
            or [{"ts": now, "value": peak_rps, "baseline": threshold}]
        add("traffic", 4, severity,
            "접속 트래픽 급증 및 처리 용량 위험" if severity == "critical" else "접속 트래픽 증가",
            f"최대 {peak_rps:.1f} req/s가 처리 기준 {threshold:.0f} req/s를 초과했습니다.",
            [f"최대 {peak_rps:.1f} req/s (임계치 {threshold:.0f} req/s)",
             f"관측 요청량 {int(request_count):,}건 / 평균 {mean_rps:.1f} req/s",
             "기준선 표본이 부족해 절대 임계값으로 판단했습니다."],
            ["백엔드 수평 확장 및 로드밸런싱", "응답 캐시 적용", "자동 확장 정책 설정"],
            {"label": "요청량 (req/s)", "points": points})


def _eval_scheduler(scheduler, now, add):
    error = _f(scheduler.get("error"))
    if error <= 0:
        return
    evidence = [f"실패 작업 {int(error)}건 / 전체 실행 {int(_f(scheduler.get('total')))}건",
                *scheduler.get("error_messages", [])]
    add("scheduler", 5, "critical", "수집 스케줄러 실행 실패",
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
    add("collection", 6, "warning", "도착정보 수집량 급감",
        f"수집 건수가 과거 같은 시간대 기준선의 {ratio:.0%} 수준으로 감소했습니다.",
        [f"수집 {int(current)}건 = 기준선({mean:.0f}±{std:.0f}건) 대비 {ratio:.0%} (z={z:.1f})",
         "외부 API 부분 실패 또는 수집 누락 가능성"],
        ["외부 API 응답 완전성 확인", "페이지별 수집 성공 여부 점검", "누락 구간 재수집"],
        {"label": "수집 건수", "points": [{"ts": now, "value": round(current, 0),
                                       "baseline": round(mean, 0)}]})


def _build_result(anomalies, pending, detected_keys, baseline, off_hours, now, cfg):
    sample_count = int(baseline.get("sample_count", 0)) if baseline else 0
    baseline_note = (f"기준선 표본 {sample_count}건 기반 통계 비교"
                     if sample_count >= cfg["min_samples"]
                     else f"기준선 표본 부족(n={sample_count}) — 절대 임계값 위주 판단")
    pending_note = ([f"관측됐으나 미확정(연속 {int(cfg['consecutive_n'])}회 필요): "
                     + ", ".join(s["title"] for s in pending)] if pending else [])

    if not anomalies:
        if off_hours:
            summary = "심야 운영 종료 시간대로, 트래픽/포화만 분석했으며 특이 이상이 없습니다."
            evidence = ["운영 종료 시간대(수집 중단)에는 API/스케줄러/수집 지표를 평가하지 않습니다.", baseline_note]
        elif pending:
            summary = ("이상 징후가 관측됐으나 연속 감지 조건을 충족하지 않아 확정하지 않았습니다.")
            evidence = [*pending_note, baseline_note]
        else:
            summary = "현재 구간에서 특이 이상이 감지되지 않았습니다."
            evidence = ["모든 golden signal(오류/지연/트래픽/포화)이 기준선·임계치 이내입니다.", baseline_note]
        return {
            "overall_status": "정상",
            "today_anomaly_count": 0,
            "detected_keys": detected_keys,
            "pending_signals": [{"key": s["key"], "title": s["title"],
                                 "severity": s["severity"]} for s in pending],
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
        "detected_keys": detected_keys,
        "pending_signals": [{"key": s["key"], "title": s["title"],
                             "severity": s["severity"]} for s in pending],
        "latest_anomaly": {"occurred_at": now, "title": primary["title"],
                           "severity": primary["severity"], "summary": primary["summary"]},
        "insights": [{"title": s["title"], "summary": s["summary"]} for s in anomalies],
        "anomalies": [{"severity": s["severity"], "title": s["title"],
                       "occurred_at": now, "category": "golden_signal"} for s in anomalies],
        "selected_anomaly_detail": {
            "title": primary["title"],
            "occurred_at": now,
            "description": primary["summary"],
            "evidence": [*primary["evidence"], *pending_note, baseline_note],
            "recommended_actions": primary["actions"],
        },
        "metric_trend": primary["trend"],
    }
