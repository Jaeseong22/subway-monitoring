"""검증 패널 — 확정된 이상을 여러 관점의 에이전트가 교차검증한다.

통계 탐지는 참이지만 실무적으로 무의미한 이상을 낼 수 있다. 배포/재시작 순간의
스파이크, 짧은 순간의 노이즈, 표본이 빈약한 기준선 등. 검증 패널은 서로 다른
관점의 심사관(lens)이 **독립적으로** "이게 진짜 조치가 필요한 이상인가"를 묻고,
다수결로 강등 여부를 정한다.

디바운스(연속 N회)가 **시간축** 오탐을 억제한다면, 이 패널은 **한 시점 안에서
여러 관점의 교차검증**으로 오탐을 억제한다. 둘은 상호 보완적이다.

핵심 설계:
- 각 렌즈는 독립적으로 판정한다(한 렌즈가 다른 렌즈 결과를 못 본다).
- LLM 호출부(llm_caller)를 주입 가능하게 해서 다수결/강등 로직을 mock으로 테스트한다.
- **강등만 한다. 승격하지 않는다.** 패널은 통계가 놓친 이상을 새로 만들지 않는다
  (판정 권한은 여전히 결정론적 탐지에 있다). 패널이 할 수 있는 건 "이건 오탐 같다"고
  다수가 보면 severity를 낮추는 것뿐.
- LLM이 없거나 실패하면 통계 판정을 그대로 둔다(패널 생략).

서드파티 의존성 없이(stdlib만) 작성한다. 실제 LLM 호출자는 주입한다.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

LOGGER = logging.getLogger("ai-service")

# llm_caller(system, user) → 판정 dict: {"verdict": "real|false_positive|uncertain", "reason": str}
LensCaller = Callable[[str, str], dict[str, Any]]

# 서로 다른 관점의 심사관. 각자 오탐의 다른 실패 모드를 노린다.
LENSES = (
    {
        "key": "deploy_noise",
        "name": "배포/재시작 회의론자",
        "system": "You judge whether an alert is just noise from a deploy, restart, or "
                  "cold start rather than a real service problem. Be skeptical: brief "
                  "spikes right after an instance (re)starts are usually noise.",
    },
    {
        "key": "persistence",
        "name": "지속성 심사관",
        "system": "You judge whether an anomaly is a momentary blip or a sustained problem. "
                  "A single-window spike that is not corroborated by sustained metrics is "
                  "likely a false positive.",
    },
    {
        "key": "evidence",
        "name": "근거 심사관",
        "system": "You judge whether the statistical evidence is solid. Weak baselines "
                  "(few samples), tiny absolute numbers, or ratios driven by near-zero "
                  "denominators make an alert untrustworthy.",
    },
)

# 심사관이 오탐이라 부를 수 있는 근거를 명확히 제한한다. 평가(evals)에서 심사관들이
# (1) 단일 인스턴스라는 이유로, (2) 충분한 baseline(40건)을 "적다"고 오판해 진짜 이상을
# 강등하는 false negative가 드러나, 아래 가드를 추가했다.
_GUARDRAILS = (
    "\n\nWhat does NOT make an alert a false positive:\n"
    "- The number of running instances. A single instance is normal — NEVER cite "
    "instance count as a reason to distrust an alert.\n"
    "- A baseline of 30+ samples. That is sufficient; only distrust the baseline when it "
    "has FEWER THAN 5 samples.\n"
    "- A large, sustained deviation. If a metric is 3x+ over a well-sampled baseline and "
    "persists for several minutes, it is a real problem regardless of instance count.\n"
    "Only call it a false positive with a concrete signal of noise: a very small baseline "
    "(<5 samples), a single-bucket momentary spike, a tiny denominator (e.g. 1 of 2 requests), "
    "or an explicit restart/deploy/scale-out warmup in the evidence."
)

_INSTRUCTION = (
    _GUARDRAILS
    + "\n\nRespond with JSON only (no markdown):\n"
    '{"verdict": "real|false_positive|uncertain", "reason": "한국어 한 문장"}\n'
    "Default to 'uncertain' if you cannot tell. Only say 'false_positive' when you have "
    "a concrete reason to distrust the alert."
)


def _build_user(anomaly: dict[str, Any], metrics: dict[str, Any], baseline: dict[str, Any]) -> str:
    latest = anomaly.get("latest_anomaly", {})
    detail = anomaly.get("selected_anomaly_detail", {})
    sample_count = 0
    if isinstance(baseline, dict):
        sample_count = int(baseline.get("sample_count", 0) or 0)
    traffic = {k: v for k, v in (metrics.get("traffic") or {}).items() if k != "points"}
    return (
        "통계 탐지가 낸 이상을 검토하라:\n"
        f"- 제목: {latest.get('title')}\n"
        f"- 심각도: {latest.get('severity')}\n"
        f"- 감지 신호: {', '.join(anomaly.get('detected_keys', []))}\n"
        f"- 근거: {json.dumps(detail.get('evidence', []), ensure_ascii=False)}\n"
        f"- 기준선 표본 수: {sample_count}\n"
        f"- API 지표: {json.dumps(metrics.get('api', {}), ensure_ascii=False, default=str)}\n"
        f"- 트래픽/포화: {json.dumps(traffic, ensure_ascii=False, default=str)}\n"
        f"- 가동 인스턴스: {traffic.get('instance_count')}"
    )


def run(anomaly: dict[str, Any], metrics: dict[str, Any], baseline: dict[str, Any],
        llm_caller: LensCaller) -> dict[str, Any]:
    """검증 패널을 돌린다.

    반환:
      {"votes": [{"lens", "verdict", "reason"}...],
       "false_positive_votes": N, "downgrade": bool, "summary": str}
    """
    user = _build_user(anomaly, metrics, baseline)
    votes: list[dict[str, Any]] = []
    for lens in LENSES:
        try:
            response = llm_caller(lens["system"] + _INSTRUCTION, user)
        except Exception as exc:
            LOGGER.warning("검증 렌즈 %s 실패: %s", lens["key"], exc)
            votes.append({"lens": lens["key"], "name": lens["name"],
                          "verdict": "uncertain", "reason": f"판정 실패: {exc}"})
            continue
        verdict = str(response.get("verdict", "uncertain")).lower()
        if verdict not in ("real", "false_positive", "uncertain"):
            verdict = "uncertain"
        votes.append({"lens": lens["key"], "name": lens["name"], "verdict": verdict,
                      "reason": str(response.get("reason", ""))[:200]})

    fp_votes = sum(1 for v in votes if v["verdict"] == "false_positive")
    # 과반(3개 중 2개 이상)이 오탐이라고 보면 강등한다.
    downgrade = fp_votes >= 2
    summary = (f"검증 패널 {len(votes)}명 중 {fp_votes}명이 오탐으로 판단"
               + (" → 강등" if downgrade else " → 판정 유지"))
    return {"votes": votes, "false_positive_votes": fp_votes,
            "downgrade": downgrade, "summary": summary}


def apply_downgrade(result: dict[str, Any], panel: dict[str, Any]) -> dict[str, Any]:
    """패널이 강등 결정을 내렸으면 판정을 한 단계 낮춘다.

    위험→주의, 주의→정상. 오탐이라고 무조건 정상으로 만들지 않고 한 단계만 낮춰,
    통계가 본 것을 완전히 버리지 않는다(패널도 틀릴 수 있으므로 보수적으로).
    이력에 강등 사실과 근거를 남긴다.
    """
    if not panel.get("downgrade"):
        return result

    downgraded = json.loads(json.dumps(result))  # 깊은 복사
    status = downgraded.get("overall_status")
    step_down = {"위험": "주의", "주의": "정상"}
    new_status = step_down.get(status, status)
    downgraded["overall_status"] = new_status
    downgraded["panel_downgraded"] = True
    downgraded["panel_summary"] = panel.get("summary", "")

    note = f"검증 패널 강등: {status} → {new_status} ({panel.get('false_positive_votes')}/3 오탐)"
    detail = downgraded.setdefault("selected_anomaly_detail", {})
    evidence = list(detail.get("evidence", []))
    evidence.append(note)
    detail["evidence"] = evidence

    if new_status == "정상":
        # 정상으로 강등되면 이상 건수를 0으로 맞춰 대시보드 표시를 일관되게 한다.
        downgraded["today_anomaly_count"] = 0
    return downgraded


def make_openai_caller(model: str | None = None, temperature: float = 0.0) -> LensCaller:
    """실제 OpenAI 판정 호출자. import를 함수 안에 두어 langchain 없이도 모듈이 import된다."""
    import os

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                     temperature=temperature,
                     model_kwargs={"response_format": {"type": "json_object"}})

    def _caller(system: str, user: str) -> dict[str, Any]:
        ai = llm.invoke([{"role": "system", "content": system},
                         {"role": "user", "content": user}])
        content = ai.content if isinstance(ai.content, str) else str(ai.content)
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"verdict": "uncertain", "reason": "응답 파싱 실패"}

    return _caller
