package com.monitoring.subway.domain.station;

import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 지하철 역 마스터 데이터.
 *
 * <p>영문명·환승 정보·설명·주변 landmark까지 여기서 관리한다. 이전에는 이 정보가
 * 프론트엔드의 하드코딩 목업(mockData.ts)에만 존재해 DB와 이원화되어 있었다.
 * 초기 데이터는 {@code resources/data/stations.json}에서 적재한다.
 */
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

    @Column(name = "name_en", length = 100)
    private String nameEn;

    @Column(name = "has_transfer", nullable = false)
    private boolean hasTransfer;

    /**
     * 노선 상의 순서(0부터). 프론트엔드 노선도가 이 순서의 배열 인덱스로 좌표를 잡으므로
     * (예: 0~20이 첫 줄, 45~64가 인천 지선) 임의로 바꾸면 노선도 레이아웃이 깨진다.
     * PK 정렬은 노선 순서와 다르기 때문에 별도 컬럼으로 보존한다.
     */
    @Column(name = "line_order", nullable = false)
    private int lineOrder;

    @Column(length = 500)
    private String description;

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "station_transfer_line", joinColumns = @JoinColumn(name = "station_id"))
    @Column(name = "line_name", length = 50)
    private List<String> transferLines = new ArrayList<>();

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "station_landmark", joinColumns = @JoinColumn(name = "station_id"))
    @Column(name = "landmark", length = 100)
    private List<String> landmarks = new ArrayList<>();

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @Builder
    public Station(String id, String name, String nameEn, boolean hasTransfer, int lineOrder,
                   String description, List<String> transferLines, List<String> landmarks) {
        this.id = id;
        this.name = name;
        this.nameEn = nameEn;
        this.hasTransfer = hasTransfer;
        this.lineOrder = lineOrder;
        this.description = description;
        this.transferLines = transferLines == null ? new ArrayList<>() : new ArrayList<>(transferLines);
        this.landmarks = landmarks == null ? new ArrayList<>() : new ArrayList<>(landmarks);
        this.createdAt = LocalDateTime.now();
    }

    public void rename(String name) {
        this.name = name;
    }

    /** 시드 데이터로 마스터 정보를 갱신한다. 이미 있는 역의 정보가 바뀌어도 반영되도록 한다. */
    public void updateDetails(String name, String nameEn, boolean hasTransfer, int lineOrder,
                              String description, List<String> transferLines, List<String> landmarks) {
        this.name = name;
        this.nameEn = nameEn;
        this.hasTransfer = hasTransfer;
        this.lineOrder = lineOrder;
        this.description = description;
        this.transferLines.clear();
        if (transferLines != null) {
            this.transferLines.addAll(transferLines);
        }
        this.landmarks.clear();
        if (landmarks != null) {
            this.landmarks.addAll(landmarks);
        }
    }
}
