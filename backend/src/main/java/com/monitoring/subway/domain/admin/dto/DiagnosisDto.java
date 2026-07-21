package com.monitoring.subway.domain.admin.dto;

import java.util.List;

/**
 * 근본 원인 진단 에이전트(RCA)의 산출물. LLM이 로그를 도구로 파고들어 찾은 원인을 담는다.
 *
 * @param status  완료 | 미결 | 생략 (생략은 rules 모드/키 없음/LLM 실패)
 * @param steps   에이전트가 실제로 실행한 조사 단계(도구 호출 과정)
 */
public record DiagnosisDto(
    boolean available,
    String status,
    String rootCause,
    String confidence,
    List<String> evidence,
    String recommendedFocus,
    int stepsUsed,
    List<StepDto> steps
) {
    public record StepDto(int step, String tool, String observation) {}

    /** 진단이 아예 없거나(rules 모드) 생략된 경우의 빈 응답. */
    public static DiagnosisDto unavailable() {
        return new DiagnosisDto(false, "생략", "", "", List.of(), "", 0, List.of());
    }
}
