package com.monitoring.subway.domain.arrival;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Table(name = "arrival_info")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ArrivalInfo {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "station_id", length = 10, nullable = false)
    private String stationId;

    // 0: 상행/내선, 1: 하행/외선
    @Column(name = "updn_line", nullable = false)
    private Integer updnLine;

    @Column(name = "train_no", length = 20)
    private String trainNo;

    @Column(name = "train_status", length = 20)
    private String trainStatus;

    @Column(length = 50)
    private String destination;

    @Column(name = "is_last_train")
    private Boolean isLastTrain;

    @Column(name = "arrival_status_msg", length = 100)
    private String arrivalStatusMsg;

    @Column(name = "expected_arrival_seconds")
    private Integer expectedArrivalSeconds;

    @Column(name = "current_station", length = 50)
    private String currentStation;

    @Column(name = "arrival_code", length = 10)
    private String arrivalCode;

    @Column(name = "station_name", length = 50)
    private String stationName;

    @Column(name = "bstatn_nm", length = 50)
    private String bstatnNm;

    @Column(name = "recptn_dt", length = 30)
    private String recptnDt;

    @Column(name = "is_skipping")
    private boolean isSkipping = false; // 무정차 통과 중인 경우 true

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @Builder
    public ArrivalInfo(String stationId, String stationName, Integer updnLine, String trainNo, String trainStatus, 
                       String destination, Boolean isLastTrain, String arrivalStatusMsg, 
                       Integer expectedArrivalSeconds, String currentStation, String arrivalCode, 
                       String bstatnNm, String recptnDt, boolean isSkipping, LocalDateTime updatedAt) {
        this.stationId = stationId;
        this.stationName = stationName;
        this.updnLine = updnLine;
        this.trainNo = trainNo;
        this.trainStatus = trainStatus;
        this.destination = destination;
        this.isLastTrain = isLastTrain;
        this.arrivalStatusMsg = arrivalStatusMsg;
        this.expectedArrivalSeconds = expectedArrivalSeconds;
        this.currentStation = currentStation;
        this.arrivalCode = arrivalCode;
        this.bstatnNm = bstatnNm;
        this.recptnDt = recptnDt;
        this.isSkipping = isSkipping;
        this.updatedAt = updatedAt;
    }
}
