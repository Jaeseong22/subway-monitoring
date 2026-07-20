package com.monitoring.subway.domain.admin;

import com.monitoring.subway.domain.admin.dto.AIInsightDto;
import com.monitoring.subway.domain.admin.dto.AdminSummaryDto;
import com.monitoring.subway.domain.admin.dto.AnomalyDto;
import com.monitoring.subway.domain.admin.dto.RemediationActionDto;
import com.monitoring.subway.domain.auth.AppUser;
import com.monitoring.subway.domain.auth.AuthGuard;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/admin")
@RequiredArgsConstructor
public class AdminController {

    private final AdminService adminService;
    private final RemediationService remediationService;
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

    /** AI가 제안한 자동 대응 조치 목록 (최신순). */
    @GetMapping("/remediation")
    public List<RemediationActionDto> getRemediationActions(
        @RequestHeader(value = "Authorization", required = false) String authorization) {
        authGuard.requireAdmin(authorization);
        return remediationService.getActions();
    }

    /** 조치 승인. 실제 확장/축소는 호스트의 워커가 수행한다. */
    @PostMapping("/remediation/{actionId}/approve")
    public RemediationActionDto approveRemediation(
        @PathVariable String actionId,
        @RequestHeader(value = "Authorization", required = false) String authorization) {
        AppUser admin = authGuard.requireAdmin(authorization);
        return remediationService.approve(actionId, admin.getEmail());
    }

    @PostMapping("/remediation/{actionId}/reject")
    public RemediationActionDto rejectRemediation(
        @PathVariable String actionId,
        @RequestHeader(value = "Authorization", required = false) String authorization) {
        AppUser admin = authGuard.requireAdmin(authorization);
        return remediationService.reject(actionId, admin.getEmail());
    }
}
