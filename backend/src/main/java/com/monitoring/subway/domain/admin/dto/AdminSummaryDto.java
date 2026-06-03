package com.monitoring.subway.domain.admin.dto;

public record AdminSummaryDto(
        String systemStatus,
        int todayAnomalyCount,
        int criticalCount,
        int warningCount,
        String latestAnomalyTitle,
        String latestAnomalyAt
) {}
