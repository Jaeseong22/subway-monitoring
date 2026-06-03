package com.monitoring.subway.domain.admin.dto;

import java.util.List;

public record AIInsightDto(
        String id,
        String category,
        String title,
        String content,
        List<String> tags
) {}
