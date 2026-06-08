package com.monitoring.subway.domain.user;

import com.monitoring.subway.domain.auth.AppUser;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(
    name = "user_station_favorite",
    uniqueConstraints = @UniqueConstraint(columnNames = {"user_id", "station_id"})
)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class UserStationFavorite {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private AppUser user;

    @Column(name = "station_id", nullable = false, length = 20)
    private String stationId;

    @Column(name = "station_name", nullable = false, length = 80)
    private String stationName;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Builder
    public UserStationFavorite(AppUser user, String stationId, String stationName) {
        this.user = user;
        this.stationId = stationId;
        this.stationName = stationName;
        this.createdAt = LocalDateTime.now();
    }

    public void renameStation(String stationName) {
        this.stationName = stationName;
    }
}
