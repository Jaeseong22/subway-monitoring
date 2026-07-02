package com.monitoring.subway.domain.admin;

import com.monitoring.subway.domain.admin.dto.AIInsightDto;
import com.monitoring.subway.domain.admin.dto.AdminSummaryDto;
import com.monitoring.subway.domain.admin.dto.AnomalyDto;
import com.monitoring.subway.domain.auth.AuthGuard;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/admin")
@RequiredArgsConstructor
public class AdminController {

    private final AdminService adminService;
    private final AuthGuard authGuard;

    @GetMapping("/anomalies")
    public List<AnomalyDto> getAnomalies(@RequestHeader(value = "Authorization", required = false) String authorization) {
        authGuard.requireAdmin(authorization);
        return adminService.getAnomalies();
    }

    @GetMapping("/insights")
    public List<AIInsightDto> getInsights(@RequestHeader(value = "Authorization", required = false) String authorization) {
        authGuard.requireAdmin(authorization);
        return adminService.getInsights();
    }

    @GetMapping("/summary")
    public AdminSummaryDto getSummary(@RequestHeader(value = "Authorization", required = false) String authorization) {
        authGuard.requireAdmin(authorization);
        return adminService.getSummary();
    }
}
