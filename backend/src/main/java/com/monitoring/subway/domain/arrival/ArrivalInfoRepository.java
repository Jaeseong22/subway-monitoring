package com.monitoring.subway.domain.arrival;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ArrivalInfoRepository extends JpaRepository<ArrivalInfo, Long> {
    List<ArrivalInfo> findByStationIdAndUpdnLineOrderByExpectedArrivalSecondsAsc(String stationId, Integer updnLine);
    Optional<ArrivalInfo> findFirstByStationIdOrderByUpdatedAtDesc(String stationId);
    Optional<ArrivalInfo> findFirstByStationIdAndExpectedArrivalSecondsBetweenOrderByExpectedArrivalSecondsAsc(
        String stationId,
        Integer minSeconds,
        Integer maxSeconds
    );
}
