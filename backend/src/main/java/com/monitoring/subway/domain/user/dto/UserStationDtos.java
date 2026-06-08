package com.monitoring.subway.domain.user.dto;

import com.monitoring.subway.domain.arrival.ArrivalInfo;
import com.monitoring.subway.domain.user.UserStationFavorite;

public class UserStationDtos {

    public record FavoriteStationResponse(
        String stationId,
        String stationName,
        String createdAt
    ) {
        public static FavoriteStationResponse from(UserStationFavorite favorite) {
            return new FavoriteStationResponse(
                favorite.getStationId(),
                favorite.getStationName(),
                favorite.getCreatedAt().toString()
            );
        }
    }

    public record StationPatternResponse(
        String stationId,
        String stationName,
        String dayOfWeek,
        int hourOfDay,
        long viewCount
    ) {}

    public record ArrivalAlertResponse(
        String stationId,
        String stationName,
        String dayOfWeek,
        int hourOfDay,
        String message,
        String arrivalStatusMsg,
        String destination,
        Integer expectedArrivalSeconds
    ) {
        public static ArrivalAlertResponse from(
            StationPatternResponse pattern,
            ArrivalInfo arrival,
            String message
        ) {
            return new ArrivalAlertResponse(
                pattern.stationId(),
                pattern.stationName(),
                pattern.dayOfWeek(),
                pattern.hourOfDay(),
                message,
                arrival.getArrivalStatusMsg(),
                arrival.getDestination(),
                arrival.getExpectedArrivalSeconds()
            );
        }
    }
}

