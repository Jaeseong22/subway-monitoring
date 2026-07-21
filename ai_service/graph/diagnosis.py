"""근본 원인 진단 에이전트 (RCA) — ReAct tool-use 루프.

탐지가 이상을 확정하면, 이 에이전트가 **로그를 스스로 파고들어** 근본 원인을 찾는다.
결정론적 규칙 엔진(detection.py)이 "무엇이 이상한가"를 판정한 뒤, 이 에이전트는
"왜 그런가"를 조사한다.

동작:
  이상 컨텍스트 → LLM에 도구(tools.py)를 쥐어줌
    → LLM이 도구를 골라 호출(가설) → 도구 실행 → 결과를 다시 LLM(관찰)
    → 반복(최대 max_steps) → 최종 근본 원인 결론

핵심 설계:
- **탐지·대응 판정을 건드리지 않는다.** 진단은 순수하게 서술적 산출물(근본 원인,
  근거, 조사 과정)이다. LLM이 없거나(rules 모드) 실패해도 판정은 그대로다.
- LLM 호출부(`llm_caller`)를 주입 가능하게 해서, LLM 없이 도구 선택/루프 로직을
  단위 테스트한다.
- 근거 없이 결론을 지어내지 않도록 프롬프트로 강제하고, 스텝을 소진하면 "미결"로 둔다.

이것이 이 시스템에서 LLM이 실제로 '에이전트'로 동작하는 유일한 지점이다:
도구를 선택하고, 관찰에 따라 다음 행동을 바꾸며, 여러 스텝을 반복한다.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable

from graph import tools

LOGGER = logging.getLogger("ai-service")

# llm_caller(messages, tool_schemas) → 응답 dict:
#   {"tool_calls": [{"id","name","arguments"}...]} 이면 도구 실행,
#   {"content": "..."} 이면 최종 답변으로 본다.
LlmCaller = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]

_SYSTEM = (
    "You are a site reliability engineer diagnosing a confirmed anomaly in a subway "
    "monitoring backend. A deterministic rule engine already decided WHAT is anomalous. "
    "Your job is to find WHY by investigating the logs with the provided tools.\n\n"
    "Rules:\n"
    "- Investigate step by step: form a hypothesis, call a tool to check it, then refine.\n"
    "- Base every claim on tool results. NEVER invent numbers or causes not seen in a tool result.\n"
    "- When you have enough evidence, stop calling tools and return a final JSON verdict.\n"
    "- If the tools do not reveal a clear cause, say so honestly with confidence 'low'.\n"
    "- Keep the investigation focused; a few well-chosen tool calls beat many.\n\n"
    "Final answer MUST be a JSON object (no markdown) with:\n"
    "{\n"
    '  "root_cause": "한국어로 근본 원인 한 문장",\n'
    '  "confidence": "high|medium|low",\n'
    '  "evidence": ["도구 결과에 근거한 관찰 (한국어)", ...],\n'
    '  "recommended_focus": "운영자가 먼저 확인할 것 (한국어)"\n'
    "}"
)


def _build_user_prompt(anomaly: dict[str, Any], metrics: dict[str, Any]) -> str:
    latest = anomaly.get("latest_anomaly", {})
    detail = anomaly.get("selected_anomaly_detail", {})
    return (
        "확정된 이상:\n"
        f"- 상태: {anomaly.get('overall_status')}\n"
        f"- 제목: {latest.get('title')}\n"
        f"- 심각도: {latest.get('severity')}\n"
        f"- 감지 신호: {', '.join(anomaly.get('detected_keys', []))}\n"
        f"- 요약: {latest.get('summary')}\n"
        f"- 통계 근거: {json.dumps(detail.get('evidence', []), ensure_ascii=False)}\n\n"
        "분석 창 지표 요약:\n"
        f"- API: {json.dumps(metrics.get('api', {}), ensure_ascii=False, default=str)}\n"
        f"- 트래픽/포화: {json.dumps({k: v for k, v in (metrics.get('traffic') or {}).items() if k != 'points'}, ensure_ascii=False, default=str)}\n"
        f"- 스케줄러: {json.dumps(metrics.get('scheduler', {}), ensure_ascii=False, default=str)}\n\n"
        "위 로그 이벤트를 도구로 조사해 근본 원인을 찾아라. 도구는 분석 창의 원시 로그 위에서 동작한다."
    )


def run(anomaly: dict[str, Any], metrics: dict[str, Any], events: list[dict[str, Any]],
        llm_caller: LlmCaller, max_steps: int = 6) -> dict[str, Any]:
    """진단 루프를 돈다. 진단 결과 dict를 반환한다(대시보드/저장용).

    반환 스키마:
      {"status": "완료|미결|생략", "root_cause": ..., "confidence": ...,
       "evidence": [...], "recommended_focus": ...,
       "investigation": [{"step", "tool", "arguments", "observation"}...],
       "steps_used": N}
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _build_user_prompt(anomaly, metrics)},
    ]
    investigation: list[dict[str, Any]] = []

    for step in range(1, max_steps + 1):
        try:
            response = llm_caller(messages, tools.TOOL_SCHEMAS)
        except Exception as exc:  # LLM 호출 자체가 실패하면 진단을 생략한다.
            LOGGER.warning("진단 LLM 호출 실패(step %d): %s", step, exc)
            return _skipped(f"LLM 호출 실패: {exc}", investigation)

        tool_calls = response.get("tool_calls") or []
        if not tool_calls:
            # 도구를 더 부르지 않으면 최종 결론으로 본다.
            verdict = _parse_verdict(response.get("content", ""))
            verdict["investigation"] = investigation
            verdict["steps_used"] = step - 1
            return verdict

        # assistant의 도구 호출 메시지를 대화에 추가한다.
        messages.append({
            "role": "assistant",
            "content": response.get("content", ""),
            "tool_calls": [
                {"id": tc.get("id", f"call_{step}_{i}"), "type": "function",
                 "function": {"name": tc["name"], "arguments": json.dumps(tc.get("arguments", {}))}}
                for i, tc in enumerate(tool_calls)
            ],
        })

        for i, call in enumerate(tool_calls):
            name = call.get("name", "")
            args = call.get("arguments", {}) or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            result = tools.dispatch(name, args, events)
            investigation.append({
                "step": step, "tool": name, "arguments": args,
                "observation": result.get("summary", ""),
            })
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", f"call_{step}_{i}"),
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

    # 스텝을 다 쓰고도 결론을 안 냈으면 미결로 둔다(억지 결론 방지).
    LOGGER.info("진단이 %d스텝 내에 결론에 도달하지 못했습니다.", max_steps)
    return {
        "status": "미결",
        "root_cause": "제한된 조사 범위에서 명확한 근본 원인을 특정하지 못했습니다.",
        "confidence": "low",
        "evidence": [i["observation"] for i in investigation[-3:]],
        "recommended_focus": "조사 범위를 넓혀 수동으로 로그를 확인하세요.",
        "investigation": investigation,
        "steps_used": max_steps,
    }


def _parse_verdict(content: str) -> dict[str, Any]:
    """LLM 최종 답변(JSON)을 파싱한다. 실패하면 원문을 근본원인으로 담아 방어한다."""
    text = str(content).strip()
    if text.startswith("```"):
        newline = text.find("\n")
        if newline != -1:
            text = text[newline + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {
            "status": "완료", "root_cause": text[:400] or "결론 파싱 실패",
            "confidence": "low", "evidence": [], "recommended_focus": "",
        }
    return {
        "status": "완료",
        "root_cause": str(parsed.get("root_cause", ""))[:400],
        "confidence": parsed.get("confidence", "low"),
        "evidence": [str(e) for e in (parsed.get("evidence") or [])][:6],
        "recommended_focus": str(parsed.get("recommended_focus", ""))[:300],
    }


def _skipped(reason: str, investigation: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "생략", "root_cause": "", "confidence": "low",
        "evidence": [], "recommended_focus": "", "reason": reason,
        "investigation": investigation, "steps_used": len(investigation),
    }


def make_openai_caller(model: str | None = None, temperature: float = 0.1) -> LlmCaller:
    """실제 OpenAI tool-use 호출자를 만든다. import를 함수 안에 두어 langchain 없이도
    이 모듈이 import되게 한다(테스트는 mock caller를 쓴다)."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                     temperature=temperature).bind_tools(tools.TOOL_SCHEMAS)

    def _caller(messages: list[dict[str, Any]], _schemas: list[dict[str, Any]]) -> dict[str, Any]:
        ai = llm.invoke(messages)
        calls = []
        for tc in getattr(ai, "tool_calls", None) or []:
            calls.append({"id": tc.get("id"), "name": tc.get("name"), "arguments": tc.get("args", {})})
        return {"content": ai.content if isinstance(ai.content, str) else str(ai.content),
                "tool_calls": calls}

    return _caller
