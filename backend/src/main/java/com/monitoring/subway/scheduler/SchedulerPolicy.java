package com.monitoring.subway.scheduler;

import org.springframework.stereotype.Component;
import java.time.LocalTime;
import java.util.concurrent.atomic.AtomicLong;

@Component
public class SchedulerPolicy {

    /**
     * 30초 주기 카운터 (내부 상태 관제용).
     *
     * <p>이 카운터는 <b>인스턴스 로컬 상태</b>다. 수집 스케줄러를 여러 인스턴스에서
     * 동시에 돌리면 인스턴스마다 카운터가 갈려 "2턴 중 1회" 주기 정책이 붕괴하고
     * 외부 API를 인스턴스 수만큼 중복 호출한다. 따라서 수집 스케줄러는
     * {@code app.scheduler.enabled=true}인 단일 프로세스에서만 실행해야 한다.
     * (여러 스레드에서의 경합만 AtomicLong으로 방지한다.)
     */
    private final AtomicLong executionCounter = new AtomicLong();

    /**
     * 운영 종료 시간인지 판별 (01:00 ~ 05:30)
     */
    public boolean isOperationEnded(LocalTime now) {
        // 01:00 ~ 05:30 중단
        if (now.isAfter(LocalTime.of(0, 59)) && now.isBefore(LocalTime.of(5, 30))) {
            return true;
        }
        return false;
    }

    public boolean isRushHour(LocalTime now) {
        // 07:00 ~ 09:00, 18:00 ~ 20:00
        boolean isMorningRush = now.isAfter(LocalTime.of(6, 59)) && now.isBefore(LocalTime.of(9, 1));
        boolean isEveningRush = now.isAfter(LocalTime.of(17, 59)) && now.isBefore(LocalTime.of(20, 1));
        return isMorningRush || isEveningRush;
    }

    /**
     * 이번 시간대의 수집 주기 설명 반환
     */
    public String getCurrentIntervalDescription(LocalTime now) {
        if (isOperationEnded(now)) return "운영 종료 (수집 중단)";
        if (isRushHour(now)) return "출퇴근 모드 (1분 주기)";
        return "일반 모드 (2분 주기)";
    }

    /**
     * 이번 턴에 스케줄을 건너뛸 것인지 반환.
     * 30초 단위 스케줄러 기준:
     * - 출퇴근 시간: 2턴 중 1회 (1분)
     * - 일반 시간: 4턴 중 1회 (2분)
     */
    public boolean shouldSkipThisTurn(LocalTime now) {
        // 증가와 판정을 한 번에 읽어 스레드 간 경합에서도 턴이 어긋나지 않게 한다.
        long turn = executionCounter.incrementAndGet();

        if (isRushHour(now)) {
            // 1분 주기: 2턴 중 1회 실행
            return turn % 2 != 0;
        }

        // 일반 시간 (2분 주기): 4턴 중 1회 실행
        return turn % 4 != 0;
    }
}
