package com.monitoring.subway.domain.station;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Table(name = "station")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Station {

    @Id
    @Column(length = 10)
    private String id;
    
    @Column(length = 50, nullable = false)
    private String name;
    
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;
    
    @Builder
    public Station(String id, String name) {
        this.id = id;
        this.name = name;
        this.createdAt = LocalDateTime.now();
    }
}
