package com.monitoring.subway.domain.user;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.monitoring.subway.domain.arrival.ArrivalInfo;
import com.monitoring.subway.domain.arrival.ArrivalInfoRepository;
import com.monitoring.subway.domain.auth.AppUser;
import com.monitoring.subway.domain.station.StationRepository;
import com.monitoring.subway.domain.user.dto.UserStationDtos.ArrivalAlertResponse;
import com.monitoring.subway.domain.user.dto.UserStationDtos.FavoriteStationResponse;
import com.monitoring.subway.domain.user.dto.UserStationDtos.StationPatternResponse;
import java.time.DayOfWeek;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;

@Service
@RequiredArgsConstructor
public class UserStationService {

    private static final int DEFAULT_DAYS = 30;
    private static final long ALERT_PATTERN_THRESHOLD = 3;
    private static final int ALERT_ARRIVAL_SECONDS = 15 * 60;

    private final UserStationFavoriteRepository favoriteRepository;
    private final StationRepository stationRepository;
    private final ArrivalInfoRepository arrivalInfoRepository;
    private final WebClient.Builder webClientBuilder;
    private final ObjectMapper objectMapper;

    @Value("${elasticsearch.url}")
    private String elasticsearchUrl;

    public List<FavoriteStationResponse> getFavorites(AppUser user) {
        return favoriteRepository.findByUserOrderByCreatedAtDesc(user).stream()
            .map(FavoriteStationResponse::from)
            .toList();
    }

    @Transactional
    public FavoriteStationResponse addFavorite(AppUser user, String stationId) {
        return favoriteRepository.findByUserAndStationId(user, stationId)
            .map(FavoriteStationResponse::from)
            .orElseGet(() -> FavoriteStationResponse.from(favoriteRepository.save(
                UserStationFavorite.builder()
                    .user(user)
                    .stationId(stationId)
                    .stationName(resolveStationName(stationId))
                    .build()
            )));
    }

    @Transactional
    public void removeFavorite(AppUser user, String stationId) {
        favoriteRepository.deleteByUserAndStationId(user, stationId);
    }

    public boolean isFavorite(AppUser user, String stationId) {
        return favoriteRepository.existsByUserAndStationId(user, stationId);
    }

    public List<StationPatternResponse> getStationPatterns(AppUser user, int days) {
        int windowDays = days > 0 ? days : DEFAULT_DAYS;
        List<UserStationFavorite> favorites = favoriteRepository.findByUserOrderByCreatedAtDesc(user);
        if (favorites.isEmpty()) {
            return List.of();
        }

        Map<String, String> favoriteNames = favorites.stream()
            .collect(Collectors.toMap(UserStationFavorite::getStationId, UserStationFavorite::getStationName));
        Set<String> favoriteIds = new HashSet<>(favoriteNames.keySet());
        List<StationPatternResponse> patterns = fetchPatterns(user.getId(), windowDays);
        return patterns.stream()
            .filter(pattern -> favoriteIds.contains(pattern.stationId()))
            .map(pattern -> new StationPatternResponse(
                pattern.stationId(),
                favoriteNames.getOrDefault(pattern.stationId(), pattern.stationName()),
                pattern.dayOfWeek(),
                pattern.hourOfDay(),
                pattern.viewCount()
            ))
            .toList();
    }

    public List<ArrivalAlertResponse> getArrivalAlerts(AppUser user) {
        LocalDateTime now = LocalDateTime.now();
        String currentDay = now.getDayOfWeek().name();
        int currentHour = now.getHour();
        List<StationPatternResponse> matchingPatterns = getStationPatterns(user, DEFAULT_DAYS).stream()
            .filter(pattern -> pattern.viewCount() >= ALERT_PATTERN_THRESHOLD)
            .filter(pattern -> currentDay.equals(pattern.dayOfWeek()))
            .filter(pattern -> currentHour == pattern.hourOfDay())
            .toList();

        List<ArrivalAlertResponse> alerts = new ArrayList<>();
        for (StationPatternResponse pattern : matchingPatterns) {
            arrivalInfoRepository.findFirstByStationIdAndExpectedArrivalSecondsBetweenOrderByExpectedArrivalSecondsAsc(
                pattern.stationId(),
                0,
                ALERT_ARRIVAL_SECONDS
            ).ifPresent(arrival -> alerts.add(ArrivalAlertResponse.from(
                pattern,
                arrival,
                buildAlertMessage(pattern, arrival)
            )));
        }
        return alerts;
    }

    private String resolveStationName(String stationId) {
        return stationRepository.findById(stationId)
            .map(station -> station.getName())
            .orElseGet(() -> arrivalInfoRepository.findFirstByStationIdOrderByUpdatedAtDesc(stationId)
                .map(ArrivalInfo::getStationName)
                .filter(name -> !name.isBlank())
                .orElse(stationId));
    }

    private List<StationPatternResponse> fetchPatterns(Long userId, int days) {
        try {
            String response = webClientBuilder
                .baseUrl(elasticsearchUrl)
                .build()
                .post()
                .uri("/subway-logs-*/_search")
                .bodyValue(buildPatternQuery(userId, days))
                .retrieve()
                .bodyToMono(String.class)
                .block();
            if (response == null || response.isBlank()) {
                return List.of();
            }
            return parsePatternResponse(response);
        } catch (Exception ignored) {
            return List.of();
        }
    }

    private Map<String, Object> buildPatternQuery(Long userId, int days) {
        Map<String, Object> query = new HashMap<>();
        query.put("size", 0);
        query.put("query", Map.of(
            "bool", Map.of(
                "filter", List.of(
                    Map.of("term", Map.of("event_type.keyword", "USER_STATION_VIEW")),
                    Map.of("term", Map.of("user_id.keyword", String.valueOf(userId))),
                    Map.of("term", Map.of("is_favorite.keyword", "true")),
                    Map.of("range", Map.of("@timestamp", Map.of("gte", "now-" + days + "d/d")))
                )
            )
        ));
        query.put("aggs", Map.of(
            "stations", Map.of(
                "terms", Map.of("field", "station_id.keyword", "size", 20),
                "aggs", Map.of(
                    "station_name", Map.of("terms", Map.of("field", "station_name.keyword", "size", 1)),
                    "days", Map.of(
                        "terms", Map.of("field", "day_of_week.keyword", "size", 7),
                        "aggs", Map.of(
                            "hours", Map.of("terms", Map.of("field", "hour_of_day.keyword", "size", 24))
                        )
                    )
                )
            )
        ));
        return query;
    }

    private List<StationPatternResponse> parsePatternResponse(String response) throws Exception {
        JsonNode root = objectMapper.readTree(response);
        List<StationPatternResponse> patterns = new ArrayList<>();
        for (JsonNode stationBucket : root.path("aggregations").path("stations").path("buckets")) {
            String stationId = stationBucket.path("key").asText();
            String stationName = stationBucket.path("station_name").path("buckets").path(0).path("key").asText(stationId);
            for (JsonNode dayBucket : stationBucket.path("days").path("buckets")) {
                String dayOfWeek = dayBucket.path("key").asText();
                for (JsonNode hourBucket : dayBucket.path("hours").path("buckets")) {
                    patterns.add(new StationPatternResponse(
                        stationId,
                        stationName,
                        dayOfWeek,
                        hourBucket.path("key").asInt(),
                        hourBucket.path("doc_count").asLong()
                    ));
                }
            }
        }
        return patterns;
    }

    private String buildAlertMessage(StationPatternResponse pattern, ArrivalInfo arrival) {
        return String.format(
            "%s %d시에 자주 확인하는 %s 열차가 %s",
            toKoreanDay(pattern.dayOfWeek()),
            pattern.hourOfDay(),
            pattern.stationName(),
            formatArrivalStatus(arrival.getArrivalStatusMsg())
        );
    }

    private String formatArrivalStatus(String arrivalStatusMsg) {
        if (arrivalStatusMsg == null || arrivalStatusMsg.isBlank()) {
            return "곧 도착합니다.";
        }
        if (arrivalStatusMsg.endsWith("도착") || arrivalStatusMsg.endsWith("출발") || arrivalStatusMsg.endsWith("진입")) {
            return arrivalStatusMsg + " 상태입니다.";
        }
        return arrivalStatusMsg + " 도착합니다.";
    }

    private String toKoreanDay(String dayOfWeek) {
        return switch (DayOfWeek.valueOf(dayOfWeek)) {
            case MONDAY -> "월요일";
            case TUESDAY -> "화요일";
            case WEDNESDAY -> "수요일";
            case THURSDAY -> "목요일";
            case FRIDAY -> "금요일";
            case SATURDAY -> "토요일";
            case SUNDAY -> "일요일";
        };
    }
}
