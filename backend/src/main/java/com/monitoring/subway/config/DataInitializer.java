package com.monitoring.subway.config;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.monitoring.subway.domain.station.Station;
import com.monitoring.subway.domain.station.StationRepository;
import com.monitoring.subway.domain.user.UserStationFavorite;
import com.monitoring.subway.domain.user.UserStationFavoriteRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 역 마스터 데이터를 {@code resources/data/stations.json}에서 적재한다.
 *
 * <p>이전에는 이 클래스가 12개 역의 이름만 Java 코드에 하드코딩했고, 나머지 역과
 * 영문명·환승·설명 정보는 프론트엔드 목업(mockData.ts)에만 있었다. 두 소스가 갈려
 * 서로 다른 역 목록을 보여주는 상태였으므로 DB를 단일 원본으로 통일한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DataInitializer implements CommandLineRunner {

    private static final String SEED_PATH = "data/stations.json";

    private final StationRepository stationRepository;
    private final UserStationFavoriteRepository favoriteRepository;
    private final ObjectMapper objectMapper;

    /** 시드 파일의 한 항목. 프론트엔드 Station 타입과 필드가 일치한다. */
    public record StationSeed(
        String id,
        String name,
        String nameEn,
        boolean hasTransfer,
        int lineOrder,
        List<String> transferLines,
        String description,
        List<String> landmarks
    ) {}

    @Override
    @Transactional
    public void run(String... args) throws Exception {
        List<StationSeed> seeds = loadSeeds();
        if (seeds.isEmpty()) {
            log.warn("역 시드 데이터가 비어 있습니다. {} 파일을 확인하세요.", SEED_PATH);
            return;
        }

        List<Station> stations = new ArrayList<>(seeds.size());
        for (StationSeed seed : seeds) {
            Station station = stationRepository.findById(seed.id())
                .map(existing -> {
                    existing.updateDetails(seed.name(), seed.nameEn(), seed.hasTransfer(),
                        seed.lineOrder(), seed.description(), seed.transferLines(), seed.landmarks());
                    return existing;
                })
                .orElseGet(() -> Station.builder()
                    .id(seed.id())
                    .name(seed.name())
                    .nameEn(seed.nameEn())
                    .hasTransfer(seed.hasTransfer())
                    .lineOrder(seed.lineOrder())
                    .description(seed.description())
                    .transferLines(seed.transferLines())
                    .landmarks(seed.landmarks())
                    .build());
            stations.add(station);
        }
        stationRepository.saveAll(stations);
        log.info("역 마스터 데이터 {}건을 적재했습니다.", stations.size());

        syncFavoriteStationNames(seeds);
    }

    private List<StationSeed> loadSeeds() throws Exception {
        ClassPathResource resource = new ClassPathResource(SEED_PATH);
        if (!resource.exists()) {
            log.warn("역 시드 파일을 찾을 수 없습니다: {}", SEED_PATH);
            return List.of();
        }
        try (InputStream input = resource.getInputStream()) {
            return objectMapper.readValue(input, new TypeReference<List<StationSeed>>() {});
        }
    }

    /** 역 이름이 바뀌었을 때 사용자의 즐겨찾기에 저장된 표시용 이름도 함께 맞춘다. */
    private void syncFavoriteStationNames(List<StationSeed> seeds) {
        Map<String, String> namesById = new HashMap<>();
        for (StationSeed seed : seeds) {
            namesById.put(seed.id(), seed.name());
        }
        for (UserStationFavorite favorite : favoriteRepository.findAll()) {
            String name = namesById.get(favorite.getStationId());
            if (name != null && !name.equals(favorite.getStationName())) {
                favorite.renameStation(name);
            }
        }
    }
}
