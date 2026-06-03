package com.monitoring.subway.config;

import com.monitoring.subway.domain.station.Station;
import com.monitoring.subway.domain.station.StationRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.CommandLineRunner;

import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Component
@RequiredArgsConstructor
public class DataInitializer implements CommandLineRunner {

    private final StationRepository stationRepository;

    @Override
    @Transactional
    public void run(String... args) throws Exception {
        if (stationRepository.count() == 0) {
            List<Station> stations = List.of(
                    new Station("1001000133", "서울역"),
                    new Station("1001000134", "시청"),
                    new Station("1063080313", "서울(경의선/기타)"),
                    new Station("1001000135", "종각"),
                    new Station("1001000136", "종로3가"),
                    new Station("1001000137", "종로5가"),
                    new Station("1001000138", "동대문"),
                    new Station("1001000128", "동묘앞"),
                    new Station("1001000129", "신설동"),
                    new Station("1001000130", "제기동"),
                    new Station("1001000131", "청량리")
            );
            stationRepository.saveAll(stations);
        }
    }
}
