package com.monitoring.subway.domain.arrival;

import com.monitoring.subway.domain.arrival.dto.ArrivalInfoDto;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.Stream;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ArrivalService {

    private final ArrivalInfoRepository arrivalInfoRepository;

    public List<ArrivalInfoDto> getStationArrivals(String stationId) {
        List<ArrivalInfo> upboundInfos = arrivalInfoRepository
                .findByStationIdAndUpdnLineOrderByExpectedArrivalSecondsAsc(stationId, 0);

        List<ArrivalInfo> downboundInfos = arrivalInfoRepository
                .findByStationIdAndUpdnLineOrderByExpectedArrivalSecondsAsc(stationId, 1);

        // Fetch Top 3 for both directions and combine them into a single list
        return Stream.concat(
                upboundInfos.stream().limit(3),
                downboundInfos.stream().limit(3)
        )
        .map(ArrivalInfoDto::from)
        .collect(Collectors.toList());
    }

    public List<ArrivalInfoDto> getAllArrivals() {
        return arrivalInfoRepository.findAll().stream()
                .map(ArrivalInfoDto::from)
                .collect(Collectors.toList());
    }
}
