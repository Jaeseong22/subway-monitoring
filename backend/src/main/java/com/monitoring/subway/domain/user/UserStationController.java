package com.monitoring.subway.domain.user;

import com.monitoring.subway.domain.auth.AppUser;
import com.monitoring.subway.domain.auth.AuthGuard;
import com.monitoring.subway.domain.user.dto.UserStationDtos.ArrivalAlertResponse;
import com.monitoring.subway.domain.user.dto.UserStationDtos.FavoriteStationResponse;
import com.monitoring.subway.domain.user.dto.UserStationDtos.StationPatternResponse;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/users/me")
@RequiredArgsConstructor
public class UserStationController {

    private final AuthGuard authGuard;
    private final UserStationService userStationService;

    @GetMapping("/favorites")
    public List<FavoriteStationResponse> getFavorites(
        @RequestHeader(value = "Authorization", required = false) String authorization
    ) {
        return userStationService.getFavorites(authGuard.requireUser(authorization));
    }

    @PostMapping("/favorites/{stationId}")
    public FavoriteStationResponse addFavorite(
        @RequestHeader(value = "Authorization", required = false) String authorization,
        @PathVariable String stationId
    ) {
        AppUser user = authGuard.requireUser(authorization);
        return userStationService.addFavorite(user, stationId);
    }

    @DeleteMapping("/favorites/{stationId}")
    public void removeFavorite(
        @RequestHeader(value = "Authorization", required = false) String authorization,
        @PathVariable String stationId
    ) {
        AppUser user = authGuard.requireUser(authorization);
        userStationService.removeFavorite(user, stationId);
    }

    @GetMapping("/station-patterns")
    public List<StationPatternResponse> getStationPatterns(
        @RequestHeader(value = "Authorization", required = false) String authorization,
        @RequestParam(defaultValue = "30") int days
    ) {
        return userStationService.getStationPatterns(authGuard.requireUser(authorization), days);
    }

    @GetMapping("/arrival-alerts")
    public List<ArrivalAlertResponse> getArrivalAlerts(
        @RequestHeader(value = "Authorization", required = false) String authorization
    ) {
        return userStationService.getArrivalAlerts(authGuard.requireUser(authorization));
    }
}
