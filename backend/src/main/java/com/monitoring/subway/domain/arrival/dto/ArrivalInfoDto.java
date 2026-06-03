package com.monitoring.subway.domain.arrival.dto;

import com.monitoring.subway.domain.arrival.ArrivalInfo;

public record ArrivalInfoDto(
        String subwayId,
        String updnLine,
        String trainLineNm,
        String statnId,
        String statnNm,
        String btrainSttus,
        String barvlDt,
        String btrainNo,
        String arvlMsg2,
        String arvlMsg3,
        String arvlCd,
        String lstcarAt,
        String bstatnNm,
        String recptnDt,
        boolean isSkipping
) {
    public static ArrivalInfoDto from(ArrivalInfo info) {
        return new ArrivalInfoDto(
                "1001", // subwayId fixed for Line 1
                String.valueOf(info.getUpdnLine()), // "0" or "1"
                info.getDestination(), // trainLineNm
                info.getStationId(), // statnId
                info.getStationName() != null ? info.getStationName() : "알 수 없음", // statnNm
                info.getTrainStatus() != null ? info.getTrainStatus() : "일반", // btrainSttus
                String.valueOf(info.getExpectedArrivalSeconds()), // barvlDt
                info.getTrainNo(), // btrainNo
                info.getArrivalStatusMsg(), // arvlMsg2
                info.getCurrentStation(), // arvlMsg3
                info.getArrivalCode(), // arvlCd
                Boolean.TRUE.equals(info.getIsLastTrain()) ? "1" : "0", // lstcarAt
                info.getBstatnNm() != null ? info.getBstatnNm() : "", // bstatnNm
                info.getRecptnDt() != null ? info.getRecptnDt() : "", // recptnDt
                info.isSkipping()
        );
    }
}
