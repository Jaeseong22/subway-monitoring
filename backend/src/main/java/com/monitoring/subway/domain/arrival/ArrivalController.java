package com.monitoring.subway.domain.arrival;

import com.monitoring.subway.domain.arrival.dto.ArrivalInfoDto;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@RestController
@RequestMapping("/api/v1/stations")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class ArrivalController {

    private final ArrivalService arrivalService;

    @GetMapping("/{stationId}/arrivals")
    public List<ArrivalInfoDto> getStationArrivals(@PathVariable(name = "stationId") String stationId) {
        long startTime = System.currentTimeMillis();
        LocalDateTime now = LocalDateTime.now();
        boolean isWeekend = now.getDayOfWeek().getValue() >= 6;
        
        try {
            MDC.put("event_type", "USER_STATION_SEARCH");
            MDC.put("station_id", stationId);
            MDC.put("day_of_week", now.getDayOfWeek().name());
            MDC.put("is_weekend", String.valueOf(isWeekend));
            MDC.put("hour_of_day", String.valueOf(now.getHour()));
            
            List<ArrivalInfoDto> arrivals = arrivalService.getStationArrivals(stationId);
            
            long duration = System.currentTimeMillis() - startTime;
            MDC.put("duration_ms", String.valueOf(duration));
            MDC.put("result_count", String.valueOf(arrivals.size()));
            log.info("지능형 사용자 메트릭 - 역: {}, 결과: {}건, 소요: {}ms", stationId, arrivals.size(), duration);
            
            return arrivals;
        } finally {
            MDC.clear();
        }
    }

    @GetMapping("/arrivals/all")
    public List<ArrivalInfoDto> getAllArrivals() {
        long startTime = System.currentTimeMillis();
        LocalDateTime now = LocalDateTime.now();
        boolean isWeekend = now.getDayOfWeek().getValue() >= 6;
        
        try {
            MDC.put("event_type", "USER_METRIC_ALL");
            MDC.put("day_of_week", now.getDayOfWeek().name());
            MDC.put("is_weekend", String.valueOf(isWeekend));
            MDC.put("hour_of_day", String.valueOf(now.getHour()));
            
            List<ArrivalInfoDto> arrivals = arrivalService.getAllArrivals();
            
            long duration = System.currentTimeMillis() - startTime;
            MDC.put("duration_ms", String.valueOf(duration));
            MDC.put("result_count", String.valueOf(arrivals.size()));
            log.info("지능형 전체 메트릭 - 결과: {}건, 소요: {}ms", arrivals.size(), duration);
            
            return arrivals;
        } finally {
            MDC.clear();
        }
    }
}
