package com.monitoring.subway.domain.admin;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.MissingNode;
import com.monitoring.subway.domain.admin.dto.AIInsightDto;
import com.monitoring.subway.domain.admin.dto.AdminSummaryDto;
import com.monitoring.subway.domain.admin.dto.AnomalyDto;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@Service
public class AdminService {

    private final WebClient.Builder webClientBuilder;
    private final ObjectMapper objectMapper;

    @Value("${elasticsearch.url}")
    private String elasticsearchUrl;

    @Value("${elasticsearch.anomaly-index}")
    private String anomalyIndex;

    public AdminService(WebClient.Builder webClientBuilder, ObjectMapper objectMapper) {
        this.webClientBuilder = webClientBuilder;
        this.objectMapper = objectMapper;
    }

    public List<AnomalyDto> getAnomalies() {
        JsonNode source = fetchLatestSource();
        if (source.isMissingNode()) {
            return Collections.emptyList();
        }

        JsonNode result = source.path("result");
        JsonNode anomalies = result.path("anomalies");
        List<AnomalyDto.MetricDto> metrics = buildMetrics(result.path("metric_trend").path("points"));
        List<String> evidence = toStringList(result.path("selected_anomaly_detail").path("evidence"));
        List<String> recommendedActions = toStringList(result.path("selected_anomaly_detail").path("recommended_actions"));
        String fallbackDescription = result.path("latest_anomaly").path("summary").asText("");
        String detailDescription = result.path("selected_anomaly_detail").path("description").asText("");
        String description = detailDescription.isBlank() ? fallbackDescription : detailDescription;

        List<AnomalyDto> items = new ArrayList<>();
        if (anomalies.isArray()) {
            int index = 1;
            for (JsonNode anomaly : anomalies) {
                String title = anomaly.path("title").asText("특이 이상 없음");
                String occurredAt = anomaly.path("occurred_at").asText(source.path("@timestamp").asText(""));
                String severity = toKoreanSeverity(anomaly.path("severity").asText("info"));
                items.add(new AnomalyDto(
                    "A" + index++,
                    title,
                    occurredAt,
                    "시스템 전반",
                    severity,
                    description,
                    fallbackDescription,
                    evidence,
                    recommendedActions,
                    metrics
                ));
            }
        }

        if (items.isEmpty()) {
            String title = result.path("latest_anomaly").path("title").asText("특이 이상 없음");
            String occurredAt = result.path("latest_anomaly").path("occurred_at").asText(source.path("@timestamp").asText(""));
            String severity = toKoreanSeverity(result.path("latest_anomaly").path("severity").asText("info"));
            items.add(new AnomalyDto(
                "A1",
                title,
                occurredAt,
                "시스템 전반",
                severity,
                description,
                fallbackDescription,
                evidence,
                recommendedActions,
                metrics
            ));
        }

        return items;
    }

    public List<AIInsightDto> getInsights() {
        JsonNode source = fetchLatestSource();
        if (source.isMissingNode()) {
            return Collections.emptyList();
        }

        JsonNode insights = source.path("result").path("insights");
        if (!insights.isArray()) {
            return Collections.emptyList();
        }

        List<AIInsightDto> items = new ArrayList<>();
        int index = 1;
        for (JsonNode insight : insights) {
            items.add(new AIInsightDto(
                "I" + index++,
                "analysis",
                insight.path("title").asText("AI 인사이트"),
                insight.path("summary").asText(""),
                Collections.emptyList()
            ));
        }
        return items;
    }

    public AdminSummaryDto getSummary() {
        JsonNode source = fetchLatestSource();
        if (source.isMissingNode()) {
            return new AdminSummaryDto("정상", 0, 0, 0, "특이 이상 없음", "");
        }

        JsonNode result = source.path("result");
        JsonNode anomalies = result.path("anomalies");
        int criticalCount = 0;
        int warningCount = 0;
        if (anomalies.isArray()) {
            for (JsonNode anomaly : anomalies) {
                String severity = toKoreanSeverity(anomaly.path("severity").asText("info"));
                if ("위험".equals(severity)) {
                    criticalCount++;
                } else if ("주의".equals(severity)) {
                    warningCount++;
                }
            }
        }

        String systemStatus = result.path("overall_status").asText("");
        if (systemStatus.isBlank()) {
            systemStatus = criticalCount > 0 ? "위험" : warningCount > 0 ? "주의" : "정상";
        }

        String latestTitle = result.path("latest_anomaly").path("title").asText("특이 이상 없음");
        String latestAt = result.path("latest_anomaly").path("occurred_at").asText(source.path("@timestamp").asText(""));
        int todayCount = result.path("today_anomaly_count").asInt(anomalies.isArray() ? anomalies.size() : 0);
        return new AdminSummaryDto(systemStatus, todayCount, criticalCount, warningCount, latestTitle, latestAt);
    }

    private JsonNode fetchLatestSource() {
        try {
            String response = webClientBuilder
                .baseUrl(elasticsearchUrl)
                .build()
                .get()
                .uri("/{index}/_search?size=1&sort=@timestamp:desc", anomalyIndex)
                .retrieve()
                .bodyToMono(String.class)
                .block(Duration.ofSeconds(10));
            if (response == null || response.isBlank()) {
                return MissingNode.getInstance();
            }
            JsonNode root = objectMapper.readTree(response);
            JsonNode hits = root.path("hits").path("hits");
            if (hits.isArray() && hits.size() > 0) {
                return hits.get(0).path("_source");
            }
        } catch (Exception ignored) {
        }
        return MissingNode.getInstance();
    }

    private List<String> toStringList(JsonNode node) {
        if (!node.isArray()) {
            return Collections.emptyList();
        }
        List<String> items = new ArrayList<>();
        for (JsonNode item : node) {
            items.add(item.asText());
        }
        return items;
    }

    private List<AnomalyDto.MetricDto> buildMetrics(JsonNode points) {
        if (!points.isArray()) {
            return Collections.emptyList();
        }
        List<AnomalyDto.MetricDto> items = new ArrayList<>();
        for (JsonNode point : points) {
            items.add(new AnomalyDto.MetricDto(
                point.path("ts").asText(""),
                point.path("value").asDouble(0.0),
                point.has("baseline") ? point.path("baseline").asDouble() : null
            ));
        }
        return items;
    }

    private String toKoreanSeverity(String severity) {
        if (severity == null) {
            return "정상";
        }
        return switch (severity.toLowerCase()) {
            case "critical" -> "위험";
            case "warning" -> "주의";
            case "info" -> "정상";
            default -> severity;
        };
    }
}
