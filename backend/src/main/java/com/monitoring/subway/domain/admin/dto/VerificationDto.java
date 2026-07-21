package com.monitoring.subway.domain.admin.dto;

import java.util.List;

/**
 * 검증 패널(멀티 에이전트 교차검증) 산출물. 여러 관점의 심사관이 이상을 오탐인지
 * 교차검증한 결과를 담는다.
 *
 * @param downgraded 과반이 오탐으로 봐서 판정이 강등되었는지
 */
public record VerificationDto(
    boolean available,
    int falsePositiveVotes,
    int totalVotes,
    boolean downgraded,
    String summary,
    List<VoteDto> votes
) {
    public record VoteDto(String lens, String name, String verdict, String reason) {}

    public static VerificationDto unavailable() {
        return new VerificationDto(false, 0, 0, false, "", List.of());
    }
}
