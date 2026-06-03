package com.monitoring.subway.domain.admin;

import com.monitoring.subway.domain.admin.dto.AIInsightDto;
import com.monitoring.subway.domain.admin.dto.AdminSummaryDto;
import com.monitoring.subway.domain.admin.dto.AnomalyDto;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v1/admin")
@RequiredArgsConstructor
@CrossOrigin(origins = "*") // 프론트엔드 연동 전용 임시 개방
public class AdminController {

    private final AdminService adminService;

    @GetMapping("/anomalies")
    public List<AnomalyDto> getAnomalies() {
        return adminService.getAnomalies();
    }

    @GetMapping("/insights")
    public List<AIInsightDto> getInsights() {
        return adminService.getInsights();
    }

    @GetMapping("/summary")
    public AdminSummaryDto getSummary() {
        return adminService.getSummary();
    }
}
