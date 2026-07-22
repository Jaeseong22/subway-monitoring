package com.monitoring.subway.domain.admin;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.monitoring.subway.domain.admin.dto.AdminSummaryDto;
import com.monitoring.subway.domain.admin.dto.DiagnosisDto;
import com.monitoring.subway.domain.admin.dto.VerificationDto;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.WebClient;

import java.io.IOException;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * AdminService가 Elasticsearch 응답을 어떻게 파싱하는지 검증한다. ES를 MockWebServer로
 * 스텁해 실제 HTTP 왕복까지 태운다(WebClient → JSON → DTO 경로 전체).
 */
class AdminServiceTest {

    private MockWebServer es;
    private AdminService service;

    @BeforeEach
    void setUp() throws IOException {
        es = new MockWebServer();
        es.start();
        service = new AdminService(WebClient.builder(), new ObjectMapper());
        ReflectionTestUtils.setField(service, "elasticsearchUrl", es.url("/").toString());
        ReflectionTestUtils.setField(service, "anomalyIndex", "subway-anomaly-results");
    }

    @AfterEach
    void tearDown() throws IOException {
        es.shutdown();
    }

    private void enqueueSource(String sourceJson) {
        String body = "{\"hits\":{\"hits\":[{\"_source\":" + sourceJson + "}]}}";
        es.enqueue(new MockResponse().setResponseCode(200)
            .setHeader("Content-Type", "application/json").setBody(body));
    }

    @Test
    void getDiagnosis_parsesRootCauseAndInvestigationSteps() {
        enqueueSource("""
            {"diagnosis":{
               "status":"완료","root_cause":"page3 호출이 타임아웃","confidence":"high",
               "evidence":["504가 page3에 100%"],"recommended_focus":"보조키 쿼터",
               "steps_used":2,
               "investigation":[
                 {"step":1,"tool":"breakdown_by","observation":"504=9"},
                 {"step":2,"tool":"time_histogram","observation":"08:15=9"}]}}
            """);

        DiagnosisDto dto = service.getDiagnosis();

        assertThat(dto.available()).isTrue();
        assertThat(dto.status()).isEqualTo("완료");
        assertThat(dto.rootCause()).contains("page3");
        assertThat(dto.confidence()).isEqualTo("high");
        assertThat(dto.stepsUsed()).isEqualTo(2);
        assertThat(dto.steps()).hasSize(2);
        assertThat(dto.steps().get(0).tool()).isEqualTo("breakdown_by");
        assertThat(dto.evidence()).containsExactly("504가 page3에 100%");
    }

    @Test
    void getDiagnosis_returnsUnavailableWhenFieldMissing() {
        enqueueSource("{\"result\":{\"overall_status\":\"정상\"}}");  // diagnosis 필드 없음
        DiagnosisDto dto = service.getDiagnosis();
        assertThat(dto.available()).isFalse();
    }

    @Test
    void getVerification_parsesVotesAndDowngrade() {
        enqueueSource("""
            {"verification":{
               "false_positive_votes":2,"downgrade":true,
               "summary":"2/3 오탐",
               "votes":[
                 {"lens":"deploy_noise","name":"배포 회의론자","verdict":"false_positive","reason":"배포 직후"},
                 {"lens":"persistence","name":"지속성","verdict":"false_positive","reason":"순간 블립"},
                 {"lens":"evidence","name":"근거","verdict":"real","reason":"표본 충분"}]}}
            """);

        VerificationDto dto = service.getVerification();

        assertThat(dto.available()).isTrue();
        assertThat(dto.downgraded()).isTrue();
        assertThat(dto.falsePositiveVotes()).isEqualTo(2);
        assertThat(dto.totalVotes()).isEqualTo(3);
        assertThat(dto.votes()).hasSize(3);
        assertThat(dto.votes().get(0).verdict()).isEqualTo("false_positive");
    }

    @Test
    void getSummary_readsOverallStatusAndCounts() {
        enqueueSource("""
            {"result":{"overall_status":"위험","today_anomaly_count":2,
               "latest_anomaly":{"title":"API 장애","occurred_at":"2026-07-22T00:00:00Z","severity":"critical"},
               "anomalies":[{"severity":"critical"},{"severity":"warning"}]}}
            """);

        AdminSummaryDto dto = service.getSummary();

        assertThat(dto.systemStatus()).isEqualTo("위험");
        assertThat(dto.criticalCount()).isEqualTo(1);
        assertThat(dto.warningCount()).isEqualTo(1);
        assertThat(dto.latestAnomalyTitle()).isEqualTo("API 장애");
    }

    @Test
    void gracefullyDegradesWhenElasticsearchUnavailable() {
        // ES가 500을 주거나 인덱스가 없어도 관제 API는 죽지 않고 기본값을 준다.
        es.enqueue(new MockResponse().setResponseCode(500));
        DiagnosisDto dto = service.getDiagnosis();
        assertThat(dto.available()).isFalse();

        es.enqueue(new MockResponse().setResponseCode(404));
        AdminSummaryDto summary = service.getSummary();
        assertThat(summary.systemStatus()).isEqualTo("정상");
        assertThat(summary.todayAnomalyCount()).isZero();
    }
}
