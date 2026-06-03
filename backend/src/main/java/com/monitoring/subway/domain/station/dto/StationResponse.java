package com.monitoring.subway.domain.station.dto;

import com.monitoring.subway.domain.station.Station;

public record StationResponse(
    String id,
    String name
) {
    public static StationResponse from(Station station) {
        return new StationResponse(station.getId(), station.getName());
    }
}
