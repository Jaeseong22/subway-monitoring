package com.monitoring.subway.domain.user;

import com.monitoring.subway.domain.auth.AppUser;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserStationFavoriteRepository extends JpaRepository<UserStationFavorite, Long> {
    List<UserStationFavorite> findByUserOrderByCreatedAtDesc(AppUser user);
    Optional<UserStationFavorite> findByUserAndStationId(AppUser user, String stationId);
    boolean existsByUserAndStationId(AppUser user, String stationId);
    void deleteByUserAndStationId(AppUser user, String stationId);
}

