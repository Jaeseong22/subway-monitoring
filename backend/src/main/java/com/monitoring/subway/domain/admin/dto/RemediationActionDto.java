package com.monitoring.subway.domain.admin.dto;

import java.util.List;

/**
 * AI가 제안한 자동 대응 조치. 관리자 대시보드에서 승인/거부한다.
 *
 * @param status PENDING / APPROVED / REJECTED / EXECUTING / EXECUTED /
 *               SUCCEEDED / FAILED / ROLLED_BACK / EXPIRED
 * @param kind   scale_out / scale_in
 */
public record RemediationActionDto(
    String id,
    String status,
    String kind,
    String reason,
    String service,
    Integer fromReplicas,
    Integer toReplicas,
    String createdAt,
    String executedAt,
    String triggerTitle,
    List<String> signalKeys,
    List<String> evidence,
    List<HistoryDto> history,
    boolean blocked,
    boolean rollback,
    boolean dryRun
) {
    public record HistoryDto(String at, String status, String note) {}
}
