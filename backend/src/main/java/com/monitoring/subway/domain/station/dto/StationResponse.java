package com.monitoring.subway.domain.station.dto;

import com.monitoring.subway.domain.station.Station;

import java.util.List;

/**
 * 역 마스터 데이터 응답. 프론트엔드의 Station 타입과 필드가 1:1로 대응한다.
 */
public record StationResponse(
    String id,
    String name,
    String nameEn,
    boolean hasTransfer,
    List<String> transferLines,
    String description,
    List<String> landmarks
) {
    public static StationResponse from(Station station) {
        return new StationResponse(
            station.getId(),
            station.getName(),
            station.getNameEn(),
            station.isHasTransfer(),
            List.copyOf(station.getTransferLines()),
            station.getDescription(),
            List.copyOf(station.getLandmarks())
        );
    }
}
