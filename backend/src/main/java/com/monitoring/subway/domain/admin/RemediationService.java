package com.monitoring.subway.domain.admin;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.monitoring.subway.domain.admin.dto.RemediationActionDto;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.server.ResponseStatusException;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * AI가 제안한 자동 대응 조치를 조회하고 승인/거부한다.
 *
 * <p>승인은 상태만 바꾼다. 실제 확장/축소는 호스트에서 도는 별도 워커
 * ({@code ai_service/remediation_worker.py})가 APPROVED 조치를 집어 실행한다.
 * API 서버가 인프라를 직접 조작하지 않도록 권한을 분리한 구조다.
 */
@Service
public class RemediationService {

    private static final String PENDING = "PENDING";
    private static final String APPROVED = "APPROVED";
    private static final String REJECTED = "REJECTED";

    private final WebClient.Builder webClientBuilder;
    private final ObjectMapper objectMapper;

    @Value("${elasticsearch.url}")
    private String elasticsearchUrl;

    @Value("${elasticsearch.remediation-index}")
    private String remediationIndex;

    public RemediationService(WebClient.Builder webClientBuilder, ObjectMapper objectMapper) {
        this.webClientBuilder = webClientBuilder;
        this.objectMapper = objectMapper;
    }

    public List<RemediationActionDto> getActions() {
        JsonNode hits = search();
        if (!hits.isArray()) {
            return Collections.emptyList();
        }
        List<RemediationActionDto> items = new ArrayList<>();
        for (JsonNode hit : hits) {
            items.add(toDto(hit.path("_id").asText(""), hit.path("_source")));
        }
        return items;
    }

    /** 승인: 워커가 집어 실행할 수 있도록 APPROVED로 전이한다. */
    public RemediationActionDto approve(String actionId, String adminEmail) {
        return transition(actionId, APPROVED, adminEmail + " 승인");
    }

    /** 거부: 더 이상 실행되지 않도록 종료 상태로 전이한다. */
    public RemediationActionDto reject(String actionId, String adminEmail) {
        return transition(actionId, REJECTED, adminEmail + " 거부");
    }

    private RemediationActionDto transition(String actionId, String nextStatus, String note) {
        ObjectNode source = fetchById(actionId);
        String current = source.path("status").asText("");
        if (!PENDING.equals(current)) {
            // 이미 실행됐거나 종료된 조치를 뒤늦게 승인하면 의도치 않은 확장이 일어난다.
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                "이미 처리된 조치입니다. (현재 상태: " + current + ")");
        }

        String now = Instant.now().toString();
        source.put("status", nextStatus);
        source.put("decided_at", now);
        source.put("decided_by", note);

        ArrayNode history = source.withArray("history");
        ObjectNode entry = history.addObject();
        entry.put("at", now);
        entry.put("status", nextStatus);
        entry.put("note", note);

        index(actionId, source);
        return toDto(actionId, source);
    }

    private JsonNode search() {
        try {
            String response = webClientBuilder
                .baseUrl(elasticsearchUrl)
                .build()
                .get()
                .uri("/{index}/_search?size=20&sort=created_at:desc", remediationIndex)
                .retrieve()
                .bodyToMono(String.class)
                .block(Duration.ofSeconds(10));
            if (response == null || response.isBlank()) {
                return objectMapper.createArrayNode();
            }
            return objectMapper.readTree(response).path("hits").path("hits");
        } catch (Exception e) {
            // 인덱스가 아직 없으면(조치가 한 번도 없었으면) 404가 난다. 빈 목록이 맞다.
            return objectMapper.createArrayNode();
        }
    }

    private ObjectNode fetchById(String actionId) {
        try {
            String response = webClientBuilder
                .baseUrl(elasticsearchUrl)
                .build()
                .get()
                .uri("/{index}/_doc/{id}", remediationIndex, actionId)
                .retrieve()
                .bodyToMono(String.class)
                .block(Duration.ofSeconds(10));
            JsonNode root = objectMapper.readTree(response);
            JsonNode source = root.path("_source");
            if (!source.isObject()) {
                throw new ResponseStatusException(HttpStatus.NOT_FOUND, "조치를 찾을 수 없습니다.");
            }
            return (ObjectNode) source;
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "조치를 찾을 수 없습니다.");
        }
    }

    private void index(String actionId, ObjectNode source) {
        try {
            webClientBuilder
                .baseUrl(elasticsearchUrl)
                .build()
                .put()
                .uri("/{index}/_doc/{id}?refresh=true", remediationIndex, actionId)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(objectMapper.writeValueAsString(source))
                .retrieve()
                .bodyToMono(String.class)
                .block(Duration.ofSeconds(10));
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                "조치 상태를 저장하지 못했습니다: " + e.getMessage());
        }
    }

    private RemediationActionDto toDto(String id, JsonNode source) {
        JsonNode params = source.path("params");
        JsonNode trigger = source.path("trigger");
        return new RemediationActionDto(
            id,
            source.path("status").asText(""),
            source.path("kind").asText(""),
            source.path("reason").asText(""),
            params.path("service").asText(""),
            params.has("from_replicas") ? params.path("from_replicas").asInt() : null,
            params.has("to_replicas") ? params.path("to_replicas").asInt() : null,
            source.path("created_at").asText(""),
            source.path("executed_at").asText(""),
            trigger.path("title").asText(""),
            toStringList(trigger.path("signal_keys")),
            toStringList(source.path("evidence")),
            toHistory(source.path("history")),
            source.path("blocked").asBoolean(false),
            source.path("is_rollback").asBoolean(false),
            source.path("dry_run").asBoolean(false)
        );
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

    private List<RemediationActionDto.HistoryDto> toHistory(JsonNode node) {
        if (!node.isArray()) {
            return Collections.emptyList();
        }
        List<RemediationActionDto.HistoryDto> items = new ArrayList<>();
        for (JsonNode item : node) {
            items.add(new RemediationActionDto.HistoryDto(
                item.path("at").asText(""),
                item.path("status").asText(""),
                item.path("note").asText("")
            ));
        }
        return items;
    }
}
