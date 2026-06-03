package com.monitoring.subway.external.seoul;

import com.monitoring.subway.external.seoul.response.SeoulSubwayResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@Slf4j
@Component
@RequiredArgsConstructor
public class SeoulSubwayClient {

    private final WebClient.Builder webClientBuilder;

    @Value("${subway.api.base-url}")
    private String baseUrl;

    @Value("${subway.api.key}")
    private String primaryKey;

    @Value("${subway.api.key-secondary}")
    private String secondaryKey;

    private int cycleCount = 0;

    public SeoulSubwayResponse getAllRealtimeArrivals(boolean isRushHour) {
        cycleCount++;
        
        // 1. 상행 주력 데이터 (Page 1: 0-999) - Primary 키 담당
        SeoulSubwayResponse totalResponse = fetchWithRetry(primaryKey, 0, 999);
        if (totalResponse == null || totalResponse.realtimeArrivalList() == null) {
            log.warn("1페이지 수집 실패(Primary), Secondary 키로 긴급 전환합니다.");
            totalResponse = fetchWithRetry(secondaryKey, 0, 999);
        }

        if (totalResponse != null && totalResponse.realtimeArrivalList() != null) {
            // 2. 하행 주력 데이터 (Page 3: 2001-3000) - Secondary 키 담당 (24시간 필수 수집)
            SeoulSubwayResponse page3 = fetchWithRetry(secondaryKey, 2001, 3000);
            if (page3 != null && page3.realtimeArrivalList() != null) {
                totalResponse.realtimeArrivalList().addAll(page3.realtimeArrivalList());
                log.debug("3페이지(하행 위주) 수집 완료: {}건", page3.realtimeArrivalList().size());
            }

            // 3. 중간 데이터 (Page 2: 1001-2000) - 출퇴근 시 필수, 평시에는 격차 수집 (한도 최적화)
            boolean shouldFetchPage2 = isRushHour || (cycleCount % 2 == 0);
            if (shouldFetchPage2) {
                String keyForPage2 = (cycleCount % 2 == 0) ? primaryKey : secondaryKey;
                SeoulSubwayResponse page2 = fetchWithRetry(keyForPage2, 1001, 2000);
                if (page2 != null && page2.realtimeArrivalList() != null) {
                    totalResponse.realtimeArrivalList().addAll(page2.realtimeArrivalList());
                    log.debug("2페이지(중간) 수집 완료: {}건", page2.realtimeArrivalList().size());
                }
            } else {
                log.debug("평시(Off-peak): 2페이지 수집을 건너뛰어 한도를 절약합니다.");
            }
        }

        log.info("API 통합 수집 완료: {}건 (RushHour: {})", 
                totalResponse != null ? totalResponse.realtimeArrivalList().size() : 0, isRushHour);
        return totalResponse;
    }

    private SeoulSubwayResponse fetchWithRetry(String key, int start, int end) {
        String url = String.format("%s/%s/json/realtimeStationArrival/%d/%d/ALL", baseUrl, key, start, end);

        try {
            return webClientBuilder.build()
                    .get()
                    .uri(url)
                    .retrieve()
                    .bodyToMono(SeoulSubwayResponse.class)
                    .block();
        } catch (Exception e) {
            log.error("Failed to fetch arrival info (Range: {}-{}). Error: {}", start, end, e.getMessage());
            return null;
        }
    }


}
