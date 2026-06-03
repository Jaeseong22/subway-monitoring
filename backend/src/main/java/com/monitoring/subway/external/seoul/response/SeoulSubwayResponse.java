package com.monitoring.subway.external.seoul.response;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record SeoulSubwayResponse(
    // Success fields
    ErrorMessage errorMessage,
    List<RealtimeStationArrival> realtimeArrivalList,
    
    // Error fields (directly at root when ERROR-337 occurs)
    Integer status,
    String code,
    String message
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record ErrorMessage(
        Integer status,
        String code,
        String message,
        Integer total
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RealtimeStationArrival(
        String subwayId,
        String updnLine,
        String trainLineNm,
        String statnFid,
        String statnTid,
        String statnId,
        String statnNm,
        String btrainSttus,
        String barvlDt,
        String btrainNo,
        String bstatnId,
        String bstatnNm,
        String recptnDt,
        String arvlMsg2,
        String arvlMsg3,
        String arvlCd,
        String lstcarAt
    ) {}
}
