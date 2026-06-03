package com.monitoring.subway.domain.admin.dto;

import java.util.List;

public record AnomalyDto(
        String id,
        String type,
        String detectedAt,
        String impactScope,
        String severity,
        String description,
        String reasoning,
        List<String> evidence,
        List<String> recommendedActions,
        List<MetricDto> metrics
) {
    public record MetricDto(
            String time,
            double value,
            Double baseline
    ) {}
}
