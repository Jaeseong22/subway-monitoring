"""자동 대응(auto-remediation) 제안·검증 로직.

탐지에서 끝나지 않고 **감지 → 제안 → 승인 → 실행 → 검증 → 롤백**의 닫힌 루프를 만든다.

설계 원칙:
- **탐지와 실행을 분리한다.** 이 모듈은 "무엇을 해야 하는가"만 계산하고 실제 실행은
  하지 않는다(부수효과 없음 → 단위 테스트 가능).
- **기본은 human-in-the-loop.** 제안은 PENDING 상태로 쌓이고 관리자가 승인해야 실행된다.
  자동 승인(`REMEDIATION_AUTO_APPROVE=true`)은 명시적으로 켜야 한다.
- **가드레일 우선.** 최대/최소 인스턴스 수, 쿨다운, 중복 제안 방지가 없으면 오탐 한 번이
  무한 확장으로 이어진다.
- **검증 없는 조치는 조치가 아니다.** 실행 후 지표를 다시 확인해 개선되지 않으면
  롤백을 제안한다.

서드파티 의존성 없이(stdlib만) 작성되어 단위 테스트가 가능하다.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

# 확장으로 완화될 수 있는 신호들. (스케줄러 실패나 외부 API 장애는 서버를 늘려도 해결되지 않는다.)
SCALE_OUT_SIGNALS = ("traffic", "saturation", "latency")

# 상태 기계
PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
EXECUTING = "EXECUTING"
EXECUTED = "EXECUTED"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
ROLLED_BACK = "ROLLED_BACK"
EXPIRED = "EXPIRED"

OPEN_STATUSES = (PENDING, APPROVED, EXECUTING, EXECUTED)
TERMINAL_STATUSES = (REJECTED, SUCCEEDED, FAILED, ROLLED_BACK, EXPIRED)

SCALE_OUT = "scale_out"
SCALE_IN = "scale_in"


def config() -> dict[str, Any]:
    def _int(key: str, default: str) -> int:
        return int(os.getenv(key, default))

    def _bool(key: str, default: str) -> bool:
        return os.getenv(key, default).strip().lower() == "true"

    return {
        "enabled": _bool("REMEDIATION_ENABLED", "true"),
        "auto_approve": _bool("REMEDIATION_AUTO_APPROVE", "false"),
        "service": os.getenv("REMEDIATION_SERVICE", "backend"),
        "max_replicas": _int("REMEDIATION_MAX_REPLICAS", "4"),
        "min_replicas": _int("REMEDIATION_MIN_REPLICAS", "1"),
        "cooldown_minutes": _int("REMEDIATION_COOLDOWN_MINUTES", "15"),
        "verify_after_minutes": _int("REMEDIATION_VERIFY_AFTER_MINUTES", "10"),
        "expire_after_minutes": _int("REMEDIATION_EXPIRE_AFTER_MINUTES", "60"),
        # 실행이 이 시간 내에 EXECUTED로 넘어가지 않으면 워커 중단으로 보고 정리한다.
        # (execute의 subprocess timeout은 300초이므로 정상이면 훨씬 빨리 넘어간다.)
        "execute_timeout_minutes": _int("REMEDIATION_EXECUTE_TIMEOUT_MINUTES", "15"),
        # 정상이 이만큼 연속되면 축소를 제안한다.
        "scale_in_after_normal_runs": _int("REMEDIATION_SCALE_IN_AFTER_NORMAL_RUNS", "6"),
        # 재계획에서 '아직 포화'로 볼 CPU 기준(추가 확장 판단용). detection의 CPU_WARN과 맞춘다.
        "cpu_warn": _int("CPU_WARN", "60"),
    }


def _parse(ts: Any) -> datetime | None:
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _now(now_iso: str | None) -> datetime:
    return _parse(now_iso) or datetime.now(timezone.utc)


def now_iso() -> str:
    """현재 시각 ISO-8601 (UTC). 상태 전이 타임스탬프용."""
    return datetime.now(timezone.utc).isoformat()


def current_replicas(metrics: dict[str, Any], cfg: dict[str, Any]) -> int:
    """관측된 가동 인스턴스 수. 지표가 없으면 최소값으로 본다."""
    traffic = (metrics or {}).get("traffic", {}) or {}
    try:
        observed = int(float(traffic.get("instance_count") or 0))
    except (TypeError, ValueError):
        observed = 0
    return max(observed, cfg["min_replicas"])


def in_cooldown(recent_actions: list[dict[str, Any]], cfg: dict[str, Any],
                now_iso: str | None = None) -> bool:
    """최근에 실행된 조치가 있으면 새 조치를 내지 않는다.

    확장 직후에는 지표가 안정될 시간이 필요하다. 쿨다운이 없으면 같은 이상을 보고
    매 실행마다 확장을 제안해 순식간에 상한까지 올라간다.
    """
    now = _now(now_iso)
    threshold = now - timedelta(minutes=cfg["cooldown_minutes"])
    for action in recent_actions or []:
        if action.get("status") in (REJECTED, EXPIRED):
            continue
        stamp = _parse(action.get("executed_at") or action.get("created_at"))
        if stamp and stamp > threshold:
            return True
    return False


def has_open_action(recent_actions: list[dict[str, Any]]) -> bool:
    """아직 처리되지 않은 제안이 있으면 중복 제안하지 않는다."""
    return any(a.get("status") in OPEN_STATUSES for a in (recent_actions or []))


def propose(result: dict[str, Any], metrics: dict[str, Any],
            recent_actions: list[dict[str, Any]] | None = None,
            normal_streak: int = 0,
            now_iso: str | None = None,
            cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """탐지 결과로부터 조치를 제안한다. 제안할 것이 없으면 None."""
    cfg = cfg or config()
    if not cfg["enabled"]:
        return None
    recent_actions = recent_actions or []
    if has_open_action(recent_actions) or in_cooldown(recent_actions, cfg, now_iso):
        return None

    now = _now(now_iso)
    replicas = current_replicas(metrics, cfg)
    confirmed = [a for a in result.get("anomalies", []) if a.get("severity") in ("warning", "critical")]
    triggering = [key for key in (result.get("detected_keys") or []) if key in SCALE_OUT_SIGNALS]

    # 1) 확장: 확장으로 완화 가능한 신호가 확정됐을 때
    if confirmed and triggering:
        if replicas >= cfg["max_replicas"]:
            # 상한에 도달하면 자동 조치 대신 사람이 봐야 한다는 사실을 남긴다.
            return _build(SCALE_OUT, replicas, replicas, result, metrics,
                          triggering, now, cfg, blocked=(
                              f"이미 최대 인스턴스 수({cfg['max_replicas']}대)에 도달해 "
                              "자동 확장으로는 더 대응할 수 없습니다. 용량 증설이나 쿼리 최적화가 필요합니다."))
        return _build(SCALE_OUT, replicas, min(replicas + 1, cfg["max_replicas"]),
                      result, metrics, triggering, now, cfg)

    # 2) 축소: 충분히 오래 정상이고 최소치보다 많이 떠 있을 때
    if (not confirmed and replicas > cfg["min_replicas"]
            and normal_streak >= cfg["scale_in_after_normal_runs"]):
        return _build(SCALE_IN, replicas, max(replicas - 1, cfg["min_replicas"]),
                      result, metrics, [], now, cfg)

    return None


def _build(kind, from_replicas, to_replicas, result, metrics, triggering, now, cfg,
           blocked: str | None = None) -> dict[str, Any]:
    traffic = (metrics or {}).get("traffic", {}) or {}
    detail = result.get("selected_anomaly_detail", {}) or {}
    severity = result.get("latest_anomaly", {}).get("severity", "info")

    if blocked:
        reason = blocked
    elif kind == SCALE_OUT:
        reason = (f"{', '.join(triggering)} 신호가 확정되어 "
                  f"{cfg['service']} 인스턴스를 {from_replicas}대에서 {to_replicas}대로 확장합니다.")
    else:
        reason = (f"충분히 오래 정상 상태가 유지되어 "
                  f"{cfg['service']} 인스턴스를 {from_replicas}대에서 {to_replicas}대로 축소합니다.")

    return {
        "created_at": now.isoformat(),
        "status": PENDING,
        "kind": kind,
        "blocked": bool(blocked),
        "reason": reason,
        "trigger": {
            "signal_keys": triggering,
            "severity": severity,
            "overall_status": result.get("overall_status"),
            "title": result.get("latest_anomaly", {}).get("title"),
        },
        "params": {
            "service": cfg["service"],
            "from_replicas": from_replicas,
            "to_replicas": to_replicas,
        },
        "observed": {
            "instance_count": from_replicas,
            "peak_requests_per_second": traffic.get("peak_requests_per_second"),
            "peak_cpu_percent": traffic.get("peak_cpu_percent"),
            "peak_memory_percent": traffic.get("peak_memory_percent"),
        },
        "evidence": list(detail.get("evidence", []))[:6],
        "guardrails": {
            "max_replicas": cfg["max_replicas"],
            "min_replicas": cfg["min_replicas"],
            "cooldown_minutes": cfg["cooldown_minutes"],
            "verify_after_minutes": cfg["verify_after_minutes"],
        },
        "history": [{"at": now.isoformat(), "status": PENDING, "note": reason}],
    }


def scale_command(action: dict[str, Any], compose_files: list[str] | None = None) -> list[str]:
    """조치를 실제 실행할 명령을 만든다. 실행은 하지 않는다(호출자 책임)."""
    params = action.get("params", {}) or {}
    service = params.get("service", "backend")
    replicas = int(params.get("to_replicas", 1))
    files = compose_files or ["docker-compose.yml", "docker-compose.scale.yml"]
    cmd = ["docker", "compose"]
    for path in files:
        cmd += ["-f", path]
    cmd += ["up", "-d", "--no-recreate", "--scale", f"{service}={replicas}"]
    return cmd


def is_ready_to_verify(action: dict[str, Any], now_iso: str | None = None,
                       cfg: dict[str, Any] | None = None) -> bool:
    """실행 후 검증 대기 시간이 지났는지."""
    cfg = cfg or config()
    if action.get("status") != EXECUTED:
        return False
    executed_at = _parse(action.get("executed_at"))
    if not executed_at:
        return False
    return _now(now_iso) >= executed_at + timedelta(minutes=cfg["verify_after_minutes"])


def verify(action: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """실행 후 지표를 다시 보고 조치의 성패를 판정한다.

    조치를 하고 끝내면 "고쳤다고 믿는 것"이지 고친 게 아니다. 촉발 신호가 사라졌는지를
    기준으로 판정하고, 남아 있으면 롤백을 권고한다.
    """
    triggering = set(action.get("trigger", {}).get("signal_keys") or [])
    still_present = set(result.get("detected_keys") or []) & triggering
    status_now = result.get("overall_status")

    if action.get("kind") == SCALE_IN:
        # 축소는 이상이 재발하지 않았는지만 본다.
        if result.get("anomalies") and status_now != "정상":
            return {"status": FAILED, "rollback": True,
                    "note": f"축소 후 상태가 {status_now}로 악화되어 롤백을 권고합니다."}
        return {"status": SUCCEEDED, "rollback": False,
                "note": "축소 후에도 정상 상태가 유지되고 있습니다."}

    if not still_present:
        return {"status": SUCCEEDED, "rollback": False,
                "note": f"촉발 신호({', '.join(sorted(triggering)) or '없음'})가 해소되었습니다."}

    return {"status": FAILED, "rollback": True,
            "note": (f"확장 후에도 {', '.join(sorted(still_present))} 신호가 지속됩니다. "
                     "확장으로 해소되지 않는 원인(외부 API 지연, 슬로우 쿼리 등)일 수 있습니다.")}


# 확장으로 해소되지 않는 근본 원인을 가리키는 진단 키워드.
# 진단(RCA 에이전트)이 이런 원인을 지목하면 추가 확장 대신 롤백 후 사람에게 넘긴다.
_NON_SCALABLE_HINTS = ("외부", "api", "타임아웃", "timeout", "쿼리", "query",
                       "slow", "슬로우", "쿼터", "quota", "upstream", "종속", "db", "디비")


def replan(failed_action: dict[str, Any], result: dict[str, Any],
           metrics: dict[str, Any] | None, diagnosis: dict[str, Any] | None,
           now_iso: str | None = None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """확장이 실패했을 때 다음 행동을 재계획한다.

    단순 롤백만 하던 것을, 상황을 보고 **추가 확장 vs 롤백**으로 나눈다.
    이때 근본 원인 진단(RCA 에이전트)의 결과를 근거로 쓴다 — 에이전트 간 협업.

    안전을 위해 **행동 결정은 결정론적**이다. LLM에 인프라 결정을 맡기지 않는다.
    반환: {"decision": "escalate|rollback", "reason": str, "next": <조치 dict>}

    - escalate: 자원이 여전히 포화이고, 상한 미달이고, 진단이 '확장으로 해결 안 되는
      원인'을 지목하지 않았을 때. 한 단계 더 확장을 제안한다(PENDING/자동승인 설정 따름).
    - rollback: 그 외. 특히 진단이 외부 API/슬로우 쿼리 등을 지목하면 확장은 무의미하므로
      되돌리고 원인 대응이 필요하다고 명시한다.
    """
    cfg = cfg or config()
    now = _now(now_iso)
    params = failed_action.get("params", {}) or {}
    current = int(float(params.get("to_replicas") or 1))
    traffic = (metrics or {}).get("traffic", {}) or {}
    try:
        cpu = float(traffic.get("peak_cpu_percent") or 0)
    except (TypeError, ValueError):
        cpu = 0.0

    triggering = set(failed_action.get("trigger", {}).get("signal_keys") or [])
    still_present = set(result.get("detected_keys") or []) & triggering

    root_cause = ""
    if diagnosis and diagnosis.get("status") == "완료":
        root_cause = str(diagnosis.get("root_cause", "")).lower()
    external_cause = any(hint in root_cause for hint in _NON_SCALABLE_HINTS)

    saturated = cpu >= cfg["cpu_warn"] or bool(still_present & {"saturation", "traffic", "latency"})
    can_escalate = (failed_action.get("kind") == SCALE_OUT
                    and current < cfg["max_replicas"]
                    and saturated
                    and not external_cause)

    if can_escalate:
        target = current + 1
        reason = (f"확장이 부족해 보입니다(포화 지속, 최대 CPU {cpu:.0f}%). "
                  f"{current}대에서 {target}대로 추가 확장을 제안합니다.")
        return {"decision": "escalate", "reason": reason,
                "next": _escalate_action(failed_action, current, target, reason, now, cfg)}

    if external_cause:
        reason = (f"확장으로 해소되지 않는 원인으로 진단되었습니다: "
                  f"{diagnosis.get('root_cause')}. 롤백 후 원인 대응(캐시/서킷브레이커/쿼리 점검)이 필요합니다.")
    elif current >= cfg["max_replicas"]:
        reason = (f"최대 인스턴스({cfg['max_replicas']}대)에서도 이상이 지속됩니다. "
                  "롤백 후 용량 증설이나 근본 대응이 필요합니다.")
    else:
        reason = "확장 후에도 이상이 지속되어 롤백합니다."
    return {"decision": "rollback", "reason": reason,
            "next": rollback_of(failed_action, now_iso=now.isoformat(), cfg=cfg)}


def _escalate_action(failed_action, from_replicas, to_replicas, reason, now, cfg) -> dict[str, Any]:
    """추가 확장 조치를 만든다. 실제 확장이므로 승인 정책(auto_approve)을 따른다."""
    status = APPROVED if cfg.get("auto_approve") else PENDING
    params = failed_action.get("params", {}) or {}
    return {
        "created_at": now.isoformat(),
        "status": status,
        "kind": SCALE_OUT,
        "blocked": False,
        "is_escalation": True,
        "escalation_of": failed_action.get("action_id"),
        "reason": reason,
        "trigger": failed_action.get("trigger", {}),
        "params": {
            "service": params.get("service", cfg["service"]),
            "from_replicas": from_replicas,
            "to_replicas": to_replicas,
        },
        "evidence": [],
        "guardrails": failed_action.get("guardrails", {}),
        "history": [{"at": now.isoformat(), "status": status, "note": reason}],
    }


def rollback_of(action: dict[str, Any], now_iso: str | None = None,
                cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """실패한 조치를 되돌리는 역방향 조치를 만든다."""
    cfg = cfg or config()
    now = _now(now_iso)
    params = action.get("params", {}) or {}
    reason = (f"직전 조치({action.get('kind')})가 지표를 개선하지 못해 "
              f"{params.get('to_replicas')}대에서 {params.get('from_replicas')}대로 되돌립니다.")
    return {
        "created_at": now.isoformat(),
        "status": APPROVED,  # 롤백은 원상복구이므로 별도 승인을 요구하지 않는다.
        "kind": SCALE_IN if action.get("kind") == SCALE_OUT else SCALE_OUT,
        "blocked": False,
        "is_rollback": True,
        "rollback_of": action.get("action_id"),
        "reason": reason,
        "trigger": action.get("trigger", {}),
        "params": {
            "service": params.get("service", cfg["service"]),
            "from_replicas": params.get("to_replicas"),
            "to_replicas": params.get("from_replicas"),
        },
        "evidence": [],
        "guardrails": action.get("guardrails", {}),
        "history": [{"at": now.isoformat(), "status": APPROVED, "note": reason}],
    }


def expire_stale(action: dict[str, Any], now_iso: str | None = None,
                 cfg: dict[str, Any] | None = None) -> bool:
    """아무도 승인하지 않은 채 오래된 제안은 만료시킨다(뒤늦은 실행 방지)."""
    cfg = cfg or config()
    if action.get("status") != PENDING:
        return False
    created = _parse(action.get("created_at"))
    if not created:
        return False
    return _now(now_iso) >= created + timedelta(minutes=cfg["expire_after_minutes"])


def _last_transition_at(action: dict[str, Any]) -> datetime | None:
    """가장 최근 상태 전이 시각. history가 없으면 created_at."""
    history = action.get("history") or []
    if history:
        return _parse(history[-1].get("at"))
    return _parse(action.get("created_at"))


def reap_stuck(action: dict[str, Any], now_iso: str | None = None,
               cfg: dict[str, Any] | None = None) -> tuple[str, str] | None:
    """워커가 중간에 죽어 멈춘 조치를 종료 상태로 되돌린다.

    이게 없으면 워커가 EXECUTING/EXECUTED에서 한 번만 죽어도 그 조치가 OPEN_STATUSES에
    영원히 남고, has_open_action이 이후 **모든** 제안을 영구 차단한다(자동 대응 전체가
    조용히 죽는 단일 장애점). expire_stale은 PENDING만 만료시키므로 여기서 실행 단계의
    stuck을 처리한다.

    반환: (새 상태, 사유) 또는 None(아직 정상 범위).

    - EXECUTING이 execute_timeout을 넘으면 → FAILED. 실제로 확장이 됐는지 불확실하므로
      롤백을 자동 생성하지 않고(위험) 사람이 실제 인스턴스 수를 확인하도록 안내한다.
    - EXECUTED가 expire_after를 넘도록 검증되지 않으면 → FAILED(검증 불가 상태).
    """
    cfg = cfg or config()
    now = _now(now_iso)
    status = action.get("status")

    if status == EXECUTING:
        entered = _last_transition_at(action)
        if entered and now >= entered + timedelta(minutes=cfg["execute_timeout_minutes"]):
            return (FAILED, f"실행이 {int(cfg['execute_timeout_minutes'])}분 내에 완료되지 "
                            "않았습니다. 워커 중단이 의심됩니다. 실제 인스턴스 수를 확인하세요.")
        return None

    if status == EXECUTED:
        executed = _parse(action.get("executed_at")) or _last_transition_at(action)
        if executed and now >= executed + timedelta(minutes=cfg["expire_after_minutes"]):
            return (FAILED, f"실행 후 {int(cfg['expire_after_minutes'])}분이 지나도 검증되지 "
                            "않았습니다. 워커 중단이 의심됩니다.")
        return None

    return None


def with_status(action: dict[str, Any], status: str, note: str = "",
                now_iso: str | None = None, **extra: Any) -> dict[str, Any]:
    """상태 전이를 이력과 함께 기록한 새 dict를 반환한다."""
    now = _now(now_iso).isoformat()
    updated = dict(action)
    updated["status"] = status
    updated.update(extra)
    history = list(action.get("history") or [])
    history.append({"at": now, "status": status, "note": note})
    updated["history"] = history
    return updated
