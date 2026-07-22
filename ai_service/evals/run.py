#!/usr/bin/env python3
"""검증 패널(verification.py) 평가 러너.

cases.jsonl의 각 케이스를 실제 검증 패널(OpenAI)로 돌려 채점한다.
축 A(판정 정확도), B(심사관 합의)를 자동 채점하고, --repeat로 축 C(일관성)를 본다.
축 D(근거 타당성)는 자동 채점 불가 — reason을 덤프해 수동 채점에 넘긴다.

ES는 필요 없다(검증 패널은 OpenAI만 쓴다). Docker 없이 로컬 실행 가능.

사용:
    cd ai_service
    set -a; source ../.env; set +a
    python evals/run.py [--repeat N] [--dump-reasons]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import verification  # noqa: E402

CASES_PATH = pathlib.Path(__file__).parent / "cases.jsonl"


def load_cases() -> list[dict]:
    cases = []
    for line in CASES_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def score_case(case: dict, caller) -> dict:
    """케이스 1회 실행 후 축 A/B 채점 결과를 반환한다."""
    inp = case["input"]
    panel = verification.run(inp["result"], inp["metrics"], inp["baseline"], caller)
    exp = case["expected"]

    downgrade = panel["downgrade"]
    fp_votes = panel["false_positive_votes"]
    # 축 B: 정답 방향 투표 수
    correct_lenses = fp_votes if exp["downgrade"] else (len(panel["votes"]) - fp_votes)

    return {
        "id": case["id"],
        "category": case["category"],
        "borderline": exp.get("borderline", False),
        "expected_downgrade": exp["downgrade"],
        "actual_downgrade": downgrade,
        "axis_a": 1 if downgrade == exp["downgrade"] else 0,
        "axis_b": correct_lenses,
        "min_correct": exp.get("min_correct_lenses", 0),
        "votes": panel["votes"],
    }


def consistency(case: dict, caller, repeat: int) -> tuple[int, list[bool]]:
    """같은 케이스를 repeat회 돌려 downgrade 결정의 안정성을 본다."""
    decisions = []
    inp = case["input"]
    for _ in range(repeat):
        panel = verification.run(inp["result"], inp["metrics"], inp["baseline"], caller)
        decisions.append(panel["downgrade"])
    stable = len(set(decisions)) == 1
    return (1 if stable else 0), decisions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=1,
                        help="일관성 축(C)을 위한 반복 횟수. 1이면 C 미채점.")
    parser.add_argument("--dump-reasons", action="store_true",
                        help="축 D(수동 채점)용으로 각 심사관의 reason을 출력.")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY가 없습니다. `set -a; source ../.env; set +a` 후 실행하세요.")
        return 2

    caller = verification.make_openai_caller()
    cases = load_cases()

    results = [score_case(c, caller) for c in cases]

    # 축 A: 경계 케이스 제외하고 합산
    graded = [r for r in results if not r["borderline"]]
    a_correct = sum(r["axis_a"] for r in graded)
    # 방향별 실패 구분
    false_neg = [r for r in graded if r["expected_downgrade"] is False and r["actual_downgrade"] is True]
    false_pos = [r for r in graded if r["expected_downgrade"] is True and r["actual_downgrade"] is False]
    b_total = sum(r["axis_b"] for r in results)
    b_max = len(results) * 3

    print("=" * 68)
    print("검증 패널 평가 결과")
    print("=" * 68)
    print(f"{'케이스':<26}{'범주':<14}{'정답':<8}{'실제':<8}{'A':<4}{'B'}")
    print("-" * 68)
    for r in results:
        exp = "강등" if r["expected_downgrade"] else "유지"
        act = "강등" if r["actual_downgrade"] else "유지"
        mark = "" if r["borderline"] else ("OK" if r["axis_a"] else "XX")
        tag = "*" if r["borderline"] else " "
        print(f"{tag}{r['id']:<25}{r['category']:<14}{exp:<8}{act:<8}{mark:<4}{r['axis_b']}/3")

    print("-" * 68)
    print(f"축 A (판정 정확도, 경계 제외): {a_correct}/{len(graded)} "
          f"= {a_correct / len(graded) * 100:.0f}%")
    print(f"    실제 이상을 강등(false negative, 위험): {len(false_neg)}건 "
          f"{[r['id'] for r in false_neg]}")
    print(f"    오탐을 유지(false positive): {len(false_pos)}건 "
          f"{[r['id'] for r in false_pos]}")
    print(f"축 B (심사관 합의): {b_total}/{b_max} = {b_total / b_max * 100:.0f}%")

    if args.repeat > 1:
        print("-" * 68)
        print(f"축 C (일관성, {args.repeat}회 반복):")
        c_stable = 0
        for c in cases:
            score, decisions = consistency(c, caller, args.repeat)
            c_stable += score
            if not score:
                print(f"    흔들림 {c['id']}: {decisions}")
        print(f"축 C: {c_stable}/{len(cases)} 케이스가 안정적")

    if args.dump_reasons:
        print("=" * 68)
        print("축 D (근거 타당성) — 수동 채점용 reason 덤프")
        print("=" * 68)
        for r in results:
            print(f"\n[{r['id']}] 정답={('강등' if r['expected_downgrade'] else '유지')}")
            for v in r["votes"]:
                print(f"  {v['name']}: {v['verdict']} — {v['reason']}")

    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
