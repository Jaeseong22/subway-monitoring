package com.monitoring.subway.domain.system;

import com.monitoring.subway.scheduler.SchedulerPolicy;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalTime;

@RestController
@RequestMapping("/api/v1/system")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class SystemStatusController {

    private final SchedulerPolicy schedulerPolicy;

    @GetMapping("/status")
    public SystemStatusResponse getStatus() {
        LocalTime now = LocalTime.now();
        return new SystemStatusResponse(
            schedulerPolicy.getCurrentIntervalDescription(now),
            schedulerPolicy.isOperationEnded(now)
        );
    }

    public record SystemStatusResponse(
        String currentInterval,
        boolean isOperationEnded
    ) {}
}
