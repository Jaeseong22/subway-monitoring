package com.monitoring.subway.domain.admin;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.monitoring.subway.domain.admin.dto.RemediationActionDto;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * RemediationService의 승인/거부 상태 전이를 검증한다. 특히 자동 대응 안전의 핵심인
 * "이미 처리된 조치는 재처리 불가(409)" 규칙을 실제 ES 왕복(MockWebServer)으로 확인한다.
 */
class RemediationServiceTest {

    private MockWebServer es;
    private RemediationService service;

    @BeforeEach
    void setUp() throws IOException {
        es = new MockWebServer();
        es.start();
        service = new RemediationService(WebClient.builder(), new ObjectMapper());
        ReflectionTestUtils.setField(service, "elasticsearchUrl", es.url("/").toString());
        ReflectionTestUtils.setField(service, "remediationIndex", "subway-remediation-actions");
    }

    @AfterEach
    void tearDown() throws IOException {
        es.shutdown();
    }

    private void enqueueJson(int code, String body) {
        es.enqueue(new MockResponse().setResponseCode(code)
            .setHeader("Content-Type", "application/json").setBody(body));
    }

    private String actionDoc(String status) {
        return """
            {"_source":{
               "status":"%s","kind":"scale_out","reason":"트래픽 급증",
               "params":{"service":"backend","from_replicas":1,"to_replicas":2},
               "trigger":{"title":"트래픽 급증","signal_keys":["traffic"]},
               "evidence":["최대 60 req/s"],"history":[]}}
            """.formatted(status);
    }

    @Test
    void getActions_parsesSearchHits() {
        enqueueJson(200, """
            {"hits":{"hits":[
              {"_id":"a1","_source":{"status":"PENDING","kind":"scale_out",
                 "params":{"service":"backend","from_replicas":1,"to_replicas":2},
                 "trigger":{"title":"트래픽 급증","signal_keys":["traffic"]}}}]}}
            """);

        List<RemediationActionDto> actions = service.getActions();

        assertThat(actions).hasSize(1);
        assertThat(actions.get(0).id()).isEqualTo("a1");
        assertThat(actions.get(0).status()).isEqualTo("PENDING");
        assertThat(actions.get(0).toReplicas()).isEqualTo(2);
    }

    @Test
    void getActions_returnsEmptyWhenIndexMissing() {
        enqueueJson(404, "{\"error\":\"index_not_found\"}");
        assertThat(service.getActions()).isEmpty();
    }

    @Test
    void approve_transitionsPendingToApproved() throws InterruptedException {
        enqueueJson(200, actionDoc("PENDING"));   // fetchById
        enqueueJson(200, "{\"result\":\"updated\"}");  // index(PUT)

        RemediationActionDto result = service.approve("a1", "admin@x");

        assertThat(result.status()).isEqualTo("APPROVED");
        es.takeRequest();  // GET _doc
        RecordedRequest put = es.takeRequest();  // PUT _doc
        assertThat(put.getMethod()).isEqualTo("PUT");
        assertThat(put.getBody().readUtf8()).contains("APPROVED").contains("admin@x");
    }

    @Test
    void reject_transitionsPendingToRejected() {
        enqueueJson(200, actionDoc("PENDING"));
        enqueueJson(200, "{\"result\":\"updated\"}");
        assertThat(service.reject("a1", "admin@x").status()).isEqualTo("REJECTED");
    }

    @Test
    void approve_alreadyApproved_throwsConflict() {
        // 이미 처리된(APPROVED) 조치를 다시 승인하면 409 — 뒤늦은 승인으로 인한 중복 확장 방지.
        enqueueJson(200, actionDoc("APPROVED"));

        assertThatThrownBy(() -> service.approve("a1", "admin@x"))
            .isInstanceOf(ResponseStatusException.class)
            .hasMessageContaining("409");
    }

    @Test
    void approve_alreadyExecuted_throwsConflict() {
        enqueueJson(200, actionDoc("EXECUTED"));
        assertThatThrownBy(() -> service.approve("a1", "admin@x"))
            .isInstanceOf(ResponseStatusException.class)
            .hasMessageContaining("409");
    }

    @Test
    void approve_missingAction_throwsNotFound() {
        enqueueJson(404, "{\"found\":false}");
        assertThatThrownBy(() -> service.approve("missing", "admin@x"))
            .isInstanceOf(ResponseStatusException.class)
            .hasMessageContaining("404");
    }
}
