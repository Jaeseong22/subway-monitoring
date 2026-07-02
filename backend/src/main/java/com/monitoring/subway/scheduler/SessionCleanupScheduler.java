package com.monitoring.subway.scheduler;

import com.monitoring.subway.domain.auth.AuthService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * 만료된 로그인 세션을 주기적으로 정리한다.
 * AuthGuard는 만료 여부만 확인하고 삭제하지 않으므로, 이 작업이 없으면
 * auth_session 테이블이 무한히 증가한다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class SessionCleanupScheduler {

    private final AuthService authService;

    // 1시간(3,600,000ms)마다 실행. 초기 지연 5분.
    @Scheduled(fixedDelay = 3_600_000L, initialDelay = 300_000L)
    public void cleanupExpiredSessions() {
        long removed = authService.purgeExpiredSessions();
        if (removed > 0) {
            log.info("만료된 로그인 세션 {}건을 정리했습니다.", removed);
        }
    }
}
