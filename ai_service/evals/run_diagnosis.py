#!/usr/bin/env python3
"""진단 에이전트(diagnosis.py) 평가 러너.

cases_diagnosis.jsonl의 각 케이스를 실제 진단 에이전트(OpenAI tool-use)로 돌려 채점한다.
- 축 A(근본원인 정확성): 별도 LLM(judge)이 정답과 대조해 0-2 채점.
- 축 B(도구 활용), C(결론 적절성), D(조사 효율): 규칙 기반 자동.

ES 불필요(진단은 OpenAI만 씀). Docker 없이 로컬 실행.

사용:
    cd ai_service
    set -a; source ../.env; set +a
    python evals/run_diagnosis.py [--dump]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import diagnosis  # noqa: E402

CASES_PATH = pathlib.Path(__file__).parent / "cases_diagnosis.jsonl"


def load_cases() -> list[dict]:
    return [json.loads(l) for l in CASES_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def judge_root_cause(expected_summary: str, actual_root_cause: str, actual_evidence: list) -> dict:
    """별도 LLM으로 근본원인 정확성을 0-2 채점한다."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.0,
                     model_kwargs={"response_format": {"type": "json_object"}})
    prompt = [
        {"role": "system", "content":
            "You grade whether an AI's diagnosed root cause matches the true root cause. "
            "Judge only semantic agreement on the CAUSE, not wording. Respond JSON: "
            '{"score": 0|1|2, "reason": "한국어 한 문장"}. '
            "2 = correctly identifies the true cause (right endpoint/code/pattern). "
            "1 = right direction but partial or vague. "
            "0 = wrong cause or invents facts not in the true cause."},
        {"role": "user", "content":
            f"실제 원인(정답): {expected_summary}\n\n"
            f"AI가 진단한 원인: {actual_root_cause}\n"
            f"AI의 근거: {json.dumps(actual_evidence, ensure_ascii=False)}"},
    ]
    try:
        resp = llm.invoke(prompt)
        content = resp.content if isinstance(resp.content, str) else str(resp.content)
        data = json.loads(content)
        score = int(data.get("score", 0))
        return {"score": max(0, min(2, score)), "reason": str(data.get("reason", ""))}
    except Exception as exc:
        return {"score": 0, "reason": f"judge 실패: {exc}"}


def score_case(case: dict, caller) -> dict:
    inp = case["input"]
    exp = case["expected"]
    result = diagnosis.run(inp["anomaly"], inp["metrics"], inp["events"], caller, max_steps=6)

    status = result.get("status")
    steps = result.get("steps_used", 0)
    investigation = result.get("investigation", [])
    resolved_expected = exp["resolution"] == "완료"

    # B. 도구 활용
    axis_b = 1 if (steps > 0 and investigation) else 0
    # C. 결론 적절성
    axis_c = 1 if status == exp["resolution"] else 0
    # D. 조사 효율
    if status == "미결" and steps >= 6:
        axis_d = 0
    elif steps == 0:
        axis_d = 0
    elif 1 <= steps <= 4:
        axis_d = 2
    else:
        axis_d = 1
    # A. 근본원인 정확성 (완료 기대 케이스만 judge)
    axis_a = None
    judge = None
    if resolved_expected:
        judge = judge_root_cause(exp["cause_summary"], result.get("root_cause", ""),
                                 result.get("evidence", []))
        axis_a = judge["score"]

    return {"id": case["id"], "category": case["category"], "resolved_expected": resolved_expected,
            "status": status, "steps": steps, "root_cause": result.get("root_cause", ""),
            "investigation": investigation, "axis_a": axis_a, "axis_b": axis_b,
            "axis_c": axis_c, "axis_d": axis_d, "judge": judge,
            "expected_resolution": exp["resolution"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", action="store_true", help="진단 원문·조사과정·judge 근거 출력")
    parser.add_argument("--repeat", type=int, default=1,
                        help="각 케이스 status 안정성 확인용 반복(멀티스텝이라 노이즈 큼)")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY가 없습니다. `set -a; source ../.env; set +a` 후 실행하세요.")
        return 2

    caller = diagnosis.make_openai_caller()
    cases = load_cases()

    if args.repeat > 1:
        # 멀티스텝 tool-use는 실행마다 흔들릴 수 있다. status 안정성만 빠르게 본다.
        print(f"status 안정성 ({args.repeat}회 반복):")
        for c in cases:
            statuses = [diagnosis.run(c["input"]["anomaly"], c["input"]["metrics"],
                                      c["input"]["events"], caller, max_steps=6).get("status")
                        for _ in range(args.repeat)]
            stable = "안정" if len(set(statuses)) == 1 else "흔들림"
            print(f"  {c['id']:<28} 정답={c['expected']['resolution']:<6} {statuses} [{stable}]")
        return 0

    results = [score_case(c, caller) for c in cases]

    print("=" * 74)
    print("진단 에이전트 평가 결과")
    print("=" * 74)
    print(f"{'케이스':<28}{'정답':<8}{'상태':<8}{'A':<5}{'B':<4}{'C':<4}{'D':<4}{'steps'}")
    print("-" * 74)
    for r in results:
        a = "-" if r["axis_a"] is None else str(r["axis_a"])
        print(f"{r['id']:<28}{r['expected_resolution']:<8}{r['status'] or '?':<8}"
              f"{a:<5}{r['axis_b']:<4}{r['axis_c']:<4}{r['axis_d']:<4}{r['steps']}")

    print("-" * 74)
    judged = [r for r in results if r["axis_a"] is not None]
    a_sum = sum(r["axis_a"] for r in judged)
    print(f"축 A (근본원인 정확성, judge, 완료기대 {len(judged)}건): {a_sum}/{len(judged) * 2} "
          f"= {a_sum / (len(judged) * 2) * 100:.0f}%")
    b_sum = sum(r["axis_b"] for r in results)
    print(f"축 B (도구 활용): {b_sum}/{len(results)}")
    c_sum = sum(r["axis_c"] for r in results)
    # 결론 오류 방향 구분
    missed = [r["id"] for r in results if r["resolved_expected"] and r["axis_c"] == 0]
    hallucinated = [r["id"] for r in results if not r["resolved_expected"] and r["axis_c"] == 0]
    print(f"축 C (결론 적절성): {c_sum}/{len(results)}")
    print(f"    있는 원인 못 찾음(미결/생략): {missed}")
    print(f"    없는 원인 지어냄(억지 완료): {hallucinated}")
    d_sum = sum(r["axis_d"] for r in results)
    print(f"축 D (조사 효율): {d_sum}/{len(results) * 2}")

    if args.dump:
        print("=" * 74)
        for r in results:
            print(f"\n[{r['id']}] 정답={r['expected_resolution']} / 실제={r['status']} (steps={r['steps']})")
            print(f"  근본원인: {r['root_cause']}")
            for s in r["investigation"]:
                print(f"    [{s['step']}] {s['tool']} → {s['observation']}")
            if r["judge"]:
                print(f"  judge A={r['judge']['score']}: {r['judge']['reason']}")

    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
