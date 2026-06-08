package com.monitoring.subway.config;

import com.monitoring.subway.domain.station.Station;
import com.monitoring.subway.domain.station.StationRepository;
import com.monitoring.subway.domain.user.UserStationFavorite;
import com.monitoring.subway.domain.user.UserStationFavoriteRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.CommandLineRunner;

import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

@Component
@RequiredArgsConstructor
public class DataInitializer implements CommandLineRunner {

    private final StationRepository stationRepository;
    private final UserStationFavoriteRepository favoriteRepository;

    @Override
    @Transactional
    public void run(String... args) throws Exception {
        Map<String, String> stationNames = Map.ofEntries(
                Map.entry("1001000124", "청량리"),
                Map.entry("1001000125", "제기동"),
                Map.entry("1001000126", "신설동"),
                Map.entry("1001000127", "동묘앞"),
                Map.entry("1001000128", "동대문"),
                Map.entry("1001000129", "종로5가"),
                Map.entry("1001000130", "종로3가"),
                Map.entry("1001000131", "종각"),
                Map.entry("1001000132", "시청"),
                Map.entry("1001000133", "서울역"),
                Map.entry("1001000134", "남영"),
                Map.entry("1063080313", "서울(경의선/기타)")
        );

        List<Station> stations = stationNames.entrySet().stream()
                .map(entry -> stationRepository.findById(entry.getKey())
                        .map(station -> {
                            if (!entry.getValue().equals(station.getName())) {
                                station.rename(entry.getValue());
                            }
                            return station;
                        })
                        .orElseGet(() -> new Station(entry.getKey(), entry.getValue())))
                .toList();
        stationRepository.saveAll(stations);

        List<UserStationFavorite> favorites = favoriteRepository.findAll();
        for (UserStationFavorite favorite : favorites) {
            String stationName = stationNames.get(favorite.getStationId());
            if (stationName != null && !stationName.equals(favorite.getStationName())) {
                favorite.renameStation(stationName);
            }
        }
    }
}
