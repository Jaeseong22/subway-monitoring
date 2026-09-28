# 진단 에이전트 평가 — 기준선 기록

`gpt-4o-mini`, temperature=0.1(진단)/0.0(judge). 8 케이스(resolved 6, unresolved 2).
축 A는 LLM-judge라 실행마다 소폭 흔들릴 수 있다.

## 기준선 #0 — 2026-07-22 (수정 전)

| 축 | 점수 | 비고 |
|---|---|---|
| A. 근본원인 정확성 (judge, 완료기대 6건) | 11/12 (92%) | 원인 명확 케이스는 잘 진단 |
| B. 도구 활용 | 8/8 (100%) | 항상 도구를 씀 |
| C. 결론 적절성 | **6/8 (75%)** | **hallucinated 2건** |
| — 있는 원인 못 찾음 | 0건 | |
| — 없는 원인 지어냄(억지 완료) | **2건** | `diffuse_errors`, `sparse_logs` |
| D. 조사 효율 | 14/16 (88%) | |

### 드러난 결함 (eval이 잡은 것)

원인 명확 케이스(6건)는 잘 진단하나(A 92%), **원인이 불명확한 케이스에서 '미결'로 두지
않고 억지 '완료' 결론을 낸다**:
- `diffuse_errors`: 오류가 5개 코드·엔드포인트에 분산 → 단일 원인 없음. 그런데 완료.
- `sparse_logs`: 총 4건뿐 → 근거 부족. 그런데 완료.

원인: (1) 프롬프트가 "근거 없으면 미결"을 confidence='low' 정도로만 언급하고 status는
강조 안 함. (2) 코드상 `status='미결'`은 max_steps 소진 시에만 나오고, LLM이 "원인을
특정할 수 없다"를 표현할 방법이 없어 뭐라도 결론 내면 '완료'가 된다.

억지 완료는 운영자에게 틀린 원인을 제시해 잘못된 대응을 유도할 수 있다.

## 수정 시도 #1 — `resolved` 필드 추가 → **실패, 원복**

억지 완료를 막으려 최종 JSON에 `"resolved": true|false`를 추가하고 false면 status를
'미결'로 매핑했다. 결과가 **더 나빠져 원복**했다.

- `resolved` 조건을 느슨하게: `saturation_traffic_driven`(원인 명확)까지 미결로 만듦.
- `resolved` 조건을 "3+ 코드 분산 또는 5건 미만"으로 엄격하게: 이번엔 과교정 —
  `api_page3_timeout`(504가 page3에 100% 집중, 명백)을 3회 모두 미결로. 명확한 원인
  다수를 미결로 만들어 기준선보다 나쁨.

**교훈**: gpt-4o-mini에게 "내가 원인을 특정했는가"라는 메타인지 이진 판단(resolved)을
맡기면 보수적으로 흔들려, 명확한 원인까지 미결로 만든다. 검증 패널(단순 분류)은
프롬프트 가드로 잘 고쳐졌지만, 진단(멀티스텝 tool-use + 메타인지)은 프롬프트로 쉽게
안 고쳐진다.

### 남은 한계 (known limitation)
원인 불명확 케이스의 억지 완료(`diffuse_errors`, `sparse_logs`)는 미해결로 남긴다.
프롬프트 튜닝으로는 부작용이 더 커서, 다른 접근이 필요하다:
- 더 강한 모델(gpt-4o 등)로 메타인지 개선
- 도구 결과에서 지배 패턴 비율을 코드로 계산해 후처리(LLM 판단 배제)
- confidence 기반 필터

억지 완료는 위험도가 중간이다(틀린 원인 제시). 하지만 진단은 **판정·대응을 바꾸지
않는 서술적 산출물**이고(대시보드 표시용), confidence 필드로 신뢰도가 함께 노출되므로,
당장의 치명적 결함은 아니다. 관찰 대상으로 둔다.

### 노이즈 주의
진단은 멀티스텝 tool-use라 실행마다 status가 흔들린다(예: `scheduler_connection_fail`이
완료/미결 오감). 단일 실행으로 점수를 비교하지 말고 `--repeat 3`으로 안정성을 함께 볼 것.
검증 패널 eval(12/12 안정)과 달리 진단 eval은 재현성이 낮다.

## 확정 기준선 — 2026-07-22 (원복 후 = #0과 동일 코드)

수정을 원복했으므로 유효 기준선은 #0이다:
- A 92% / B 100% / C 75%(hallucinated 2건) / D 88%.
이후 진단 에이전트를 건드리면 이 값과 비교한다. 단일 실행 노이즈를 감안해 경향으로 본다.

### 재현
```bash
cd ai_service
set -a; source ../.env; set +a
python evals/run_diagnosis.py            # A(judge), B, C, D
python evals/run_diagnosis.py --repeat 3 # status 안정성(노이즈 확인)
python evals/run_diagnosis.py --dump     # 진단 원문·조사과정·judge 근거
```

## 실행 #2 — 2026-09-28 (모델 교체: gemini-3.1-flash-lite, 무료 티어)

| 축 | gpt-4o-mini (기준선) | gemini-3.1-flash-lite |
|---|---|---|
| A. 근본원인 정확성 (완료기대 6건) | 11/12 (92%) | **12/12 (100%)** |
| B. 도구 활용 | 8/8 (100%) | 8/8 (100%) |
| C. 결론 적절성 | 6/8 (75%), 억지 완료 2건 | **7/8 (88%), 억지 완료 1건** |
| — 있는 원인 못 찾음 | 0건 | 0건 |
| — 없는 원인 지어냄 | `diffuse_errors`, `sparse_logs` | `sparse_logs` |
| D. 조사 효율 | 14/16 (88%) | 13/16 (81%) |

A·C가 오르고 D만 조금 내렸다(스텝을 더 쓴다). **기준선 #0에서 고치지 못하고 "알려진
한계"로 남겼던 억지 완료 2건 중 `diffuse_errors`는 모델을 바꾸니 해결됐다.** 프롬프트로
못 고친 메타인지 문제가 모델 교체로 풀린 사례다. `sparse_logs`는 여전히 남는다.

### 먼저 고쳐야 했던 것: Gemini 3의 thought_signature

바꾸자마자 8케이스 전부 `생략`, A 0%가 나왔다. 원인은 모델 성능이 아니라 프로토콜이다.

```
400 INVALID_ARGUMENT: Function call is missing a thought_signature in functionCall parts
```

Gemini 3 계열은 도구 호출 응답에 `extra_content.google.thought_signature`를 실어 보내고,
**다음 턴에 그걸 그대로 돌려줘야** 대화를 이어준다. 안 돌려주면 2스텝째에 400이 나므로
ReAct 루프가 통째로 죽는다(1스텝짜리 호출은 멀쩡해서 연결 테스트로는 안 잡힌다).

`langchain-openai 0.1.23`은 이 값을 보낼 수 없다 — `_convert_message_to_dict`가 도구
호출을 `{"id", "type", "function"}`으로 **명시적으로 필터링**하고, dict를 메시지로 바꾸는
`convert_to_messages`도 미지의 키를 버린다. 메시지 dict에 넣어봐야 전송 직전에 사라진다.

그래서 진단 호출자만 langchain을 걷어내고 OpenAI SDK를 직접 쓴다(`make_openai_caller`).
루프가 이미 평범한 dict로 메시지를 주고받으므로 교체 지점은 그 함수 하나뿐이다.
받은 `extra_content`를 그대로 되돌려주도록 `_assistant_tool_call`에 보존 로직을 뒀고,
`tests/test_diagnosis.py`에 왕복 테스트 2종을 추가했다.
