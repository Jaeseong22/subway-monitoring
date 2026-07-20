package com.monitoring.subway.domain.station;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface StationRepository extends JpaRepository<Station, String> {

    /**
     * 노선 순서대로 정렬해 반환한다. 기본 findAll()은 PK 순서라 노선 순서와 다르고,
     * 프론트엔드 노선도는 배열 인덱스로 좌표를 잡으므로 순서가 어긋나면 레이아웃이 깨진다.
     */
    List<Station> findAllByOrderByLineOrderAsc();

    List<Station> findByNameContainingOrderByLineOrderAsc(String keyword);
}
