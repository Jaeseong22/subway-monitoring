package com.monitoring.subway.scheduler;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.LocalTime;
import org.junit.jupiter.api.Test;

class SchedulerPolicyTest {

    private final SchedulerPolicy policy = new SchedulerPolicy();

    @Test
    void operationEndedWindowIsExclusiveAtBoundaries() {
        // 01:00 ~ 05:30 사이는 운영 종료
        assertTrue(policy.isOperationEnded(LocalTime.of(1, 0)));
        assertTrue(policy.isOperationEnded(LocalTime.of(3, 0)));
        assertTrue(policy.isOperationEnded(LocalTime.of(5, 29)));
        // 경계 밖
        assertFalse(policy.isOperationEnded(LocalTime.of(0, 59)));
        assertFalse(policy.isOperationEnded(LocalTime.of(5, 30)));
        assertFalse(policy.isOperationEnded(LocalTime.of(12, 0)));
    }

    @Test
    void rushHourCoversMorningAndEveningPeaks() {
        assertTrue(policy.isRushHour(LocalTime.of(7, 0)));
        assertTrue(policy.isRushHour(LocalTime.of(9, 0)));
        assertTrue(policy.isRushHour(LocalTime.of(18, 0)));
        assertTrue(policy.isRushHour(LocalTime.of(20, 0)));
        assertFalse(policy.isRushHour(LocalTime.of(6, 59)));
        assertFalse(policy.isRushHour(LocalTime.of(12, 0)));
        assertFalse(policy.isRushHour(LocalTime.of(22, 0)));
    }

    @Test
    void intervalDescriptionReflectsPolicy() {
        assertEquals("운영 종료 (수집 중단)", policy.getCurrentIntervalDescription(LocalTime.of(2, 0)));
        assertEquals("출퇴근 모드 (1분 주기)", policy.getCurrentIntervalDescription(LocalTime.of(8, 0)));
        assertEquals("일반 모드 (2분 주기)", policy.getCurrentIntervalDescription(LocalTime.of(14, 0)));
    }

    @Test
    void rushHourRunsEveryOtherTurn() {
        SchedulerPolicy p = new SchedulerPolicy();
        LocalTime rush = LocalTime.of(8, 0);
        // 30초 x 2턴 중 1회 실행: 첫 턴 skip, 두 번째 턴 실행
        assertTrue(p.shouldSkipThisTurn(rush));   // counter=1
        assertFalse(p.shouldSkipThisTurn(rush));  // counter=2 -> 실행
        assertTrue(p.shouldSkipThisTurn(rush));   // counter=3
        assertFalse(p.shouldSkipThisTurn(rush));  // counter=4 -> 실행
    }

    @Test
    void normalHoursRunEveryFourthTurn() {
        SchedulerPolicy p = new SchedulerPolicy();
        LocalTime normal = LocalTime.of(14, 0);
        assertTrue(p.shouldSkipThisTurn(normal));   // 1
        assertTrue(p.shouldSkipThisTurn(normal));   // 2
        assertTrue(p.shouldSkipThisTurn(normal));   // 3
        assertFalse(p.shouldSkipThisTurn(normal));  // 4 -> 실행
    }
}
