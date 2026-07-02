package com.monitoring.subway.domain.station;

import com.monitoring.subway.domain.station.dto.StationResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/stations")
@RequiredArgsConstructor
public class StationController {

    private final StationService stationService;

    @GetMapping
    public List<StationResponse> getStations() {
        return stationService.getAllStations();
    }

    @GetMapping("/search")
    public List<StationResponse> searchStations(@RequestParam(name = "keyword", required = false) String keyword) {
        return stationService.searchStations(keyword);
    }
}
