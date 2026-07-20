package com.monitoring.subway.domain.station;

import com.monitoring.subway.domain.station.dto.StationResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class StationService {

    private final StationRepository stationRepository;

    public List<StationResponse> getAllStations() {
        return stationRepository.findAllByOrderByLineOrderAsc().stream()
                .map(StationResponse::from)
                .collect(Collectors.toList());
    }

    public List<StationResponse> searchStations(String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return getAllStations();
        }
        return stationRepository.findByNameContainingOrderByLineOrderAsc(keyword).stream()
                .map(StationResponse::from)
                .collect(Collectors.toList());
    }
}
