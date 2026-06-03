package com.monitoring.subway.scheduler;

import com.monitoring.subway.domain.arrival.ArrivalInfo;
import com.monitoring.subway.domain.arrival.ArrivalInfoRepository;
import com.monitoring.subway.external.seoul.SeoulSubwayClient;
import com.monitoring.subway.external.seoul.response.SeoulSubwayResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import jakarta.annotation.PostConstruct;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Component
@RequiredArgsConstructor
public class ArrivalUpdateScheduler {

    private final SeoulSubwayClient subwayClient;
    private final ArrivalInfoRepository arrivalInfoRepository;
    private final SchedulerPolicy schedulerPolicy;

    @PostConstruct
    public void init() {
        log.info("서비스 시작: 초기 실시간 데이터 수집을 시도합니다.");
        fetchAndSaveArrivalInfoInternal(true);
    }

    // 30초(30,000ms) 주기 고정
    @Scheduled(fixedDelay = 30000)
    @Transactional
    public void fetchAndSaveArrivalInfo() {
        fetchAndSaveArrivalInfoInternal(false);
    }

    private void fetchAndSaveArrivalInfoInternal(boolean isInitial) {
        LocalTime now = LocalTime.now();

        // 1. 운영 시간 체크 (01:00 ~ 05:00 수집 금지)
        if (schedulerPolicy.isOperationEnded(now)) {
            // 심야 시간에는 로그를 1시간에 한 번만 남기도록 제한하거나, 필요 시 생략 가능
            if (now.getMinute() == 0 && now.getSecond() < 30) {
                 log.info("지하철 운영 종료 시간대(01:00~05:00)입니다. 데이터 수집을 중단합니다.");
            }
            return;
        }

        // 2. 시간대별 주기 체크 (초기 실행이 아닐 때만 적용)
        String intervalDesc = schedulerPolicy.getCurrentIntervalDescription(now);
        if (!isInitial && schedulerPolicy.shouldSkipThisTurn(now)) {
            log.info("{} 적용: 이번 턴(30s)은 수집을 건너뜁니다.", intervalDesc);
            return;
        }

        log.info("{} 적용: 실시간 데이터 수집을 시작합니다.", intervalDesc);

        log.info("실시간 지하철 1호선 도착 정보 수집 시작...");
        long startTime = System.currentTimeMillis();
        
        try {
            SeoulSubwayResponse response = subwayClient.getAllRealtimeArrivals(schedulerPolicy.isRushHour(now));
            if (response == null || response.realtimeArrivalList() == null) {
                log.warn("API 정상 응답을 받았으나 도착 정보 목록이 비어있습니다.");
                return;
            }

            List<ArrivalInfo> allLine1Arrivals = response.realtimeArrivalList().stream()
                .filter(a -> "1001".equals(a.subwayId()))
                .map(a -> {
                    String mappedId = a.statnId() != null ? a.statnId() : "";
                    
                    return ArrivalInfo.builder()
                        .stationId(mappedId)
                        .stationName(a.statnNm())
                        .updnLine("상행".equals(a.updnLine()) || "0".equals(a.updnLine()) ? 0 : 1)
                        .trainNo(a.btrainNo())
                        .trainStatus(a.btrainSttus())
                        .destination(a.trainLineNm())
                        .isLastTrain("1".equals(a.lstcarAt()))
                        .arrivalStatusMsg(a.arvlMsg2())
                        .arrivalCode(a.arvlCd())
                        .currentStation(a.arvlMsg3())
                        .expectedArrivalSeconds(parseSeconds(a.barvlDt()))
                        .bstatnNm(a.bstatnNm())
                        .recptnDt(a.recptnDt())
                        .isSkipping(
                            (a.arvlMsg2() != null && a.arvlMsg2().contains("무정차")) ||
                            (a.arvlMsg3() != null && a.arvlMsg3().contains("무정차"))
                        )
                        .updatedAt(LocalDateTime.now())
                        .build();
                })
                .collect(Collectors.toList());

            long upCount = allLine1Arrivals.stream().filter(a -> a.getUpdnLine() == 0).count();
            long downCount = allLine1Arrivals.stream().filter(a -> a.getUpdnLine() == 1).count();

            if (allLine1Arrivals.isEmpty()) {
                log.warn("API 호출은 수행되었으나 저장할 1호선 도착정보가 0건입니다.");
                return;
            }

            // [사용자 피드백 반영]: AI 분석용 통합 메트릭 리포팅 (하드코딩 알람 최소화)
            org.slf4j.MDC.put("event_type", "METRIC_COLLECTION");
            org.slf4j.MDC.put("up_count", String.valueOf(upCount));
            org.slf4j.MDC.put("down_count", String.valueOf(downCount));
            org.slf4j.MDC.put("fetched_total", String.valueOf(response.realtimeArrivalList().size()));
            org.slf4j.MDC.put("line1_saved", String.valueOf(allLine1Arrivals.size()));
            org.slf4j.MDC.put("time_category", schedulerPolicy.isOperationEnded(now) ? "OFF" : 
                (schedulerPolicy.getCurrentIntervalDescription(now).contains("출퇴근") ? "RUSH_HOUR" : "NORMAL"));
            
            // 전체 삭제 후 삽입 (현재 상태 최신화 방식)
            arrivalInfoRepository.deleteAllInBatch();
            arrivalInfoRepository.saveAll(allLine1Arrivals);

            long duration = System.currentTimeMillis() - startTime;
            LocalDateTime nowLog = LocalDateTime.now();
            boolean isWeekend = nowLog.getDayOfWeek().getValue() >= 6; // SAT(6), SUN(7)
            
            org.slf4j.MDC.put("duration_ms", String.valueOf(duration));
            org.slf4j.MDC.put("day_of_week", nowLog.getDayOfWeek().name());
            org.slf4j.MDC.put("is_weekend", String.valueOf(isWeekend));
            org.slf4j.MDC.put("hour_of_day", String.valueOf(nowLog.getHour()));

            log.info("지능형 메트릭 수집 완료 - 상행: {}, 하행: {}, 저장: {}건, 소요: {}ms",
                    upCount, downCount, allLine1Arrivals.size(), duration);

            // [AI 관제 전전용]: 동적 임계값 기반 혼잡도 분석 (유지)
            var stationCounts = allLine1Arrivals.stream()
                .collect(Collectors.groupingBy(ArrivalInfo::getStationName, Collectors.counting()));
            
            double avgCount = stationCounts.values().stream().mapToLong(Long::longValue).average().orElse(0.0);
            
            stationCounts.forEach((stationName, count) -> {
                if (count >= 6 && count > avgCount * 3) { 
                    org.slf4j.MDC.put("event_type", "STATION_CONGESTION_ALERT");
                    org.slf4j.MDC.put("congestion_station", stationName);
                    org.slf4j.MDC.put("congestion_count", String.valueOf(count));
                    org.slf4j.MDC.put("average_count", String.format("%.2f", avgCount));
                    log.warn("🚨 [동적 혼잡 감지]: {}역에 {}대의 열차가 밀집(노선 평균: {:.2f}). 대규모 행사 가능성이 높습니다.", 
                            stationName, count, avgCount);
                }
            });

        } catch (Exception e) {
            org.slf4j.MDC.put("event_type", "SYSTEM_FETCH_ERROR");
            log.error("도착 정보 수집/저장 중 오류 발생", e);
        } finally {
            org.slf4j.MDC.clear();
        }
    }

    private Integer parseSeconds(String val) {
        try {
            return Integer.parseInt(val);
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
