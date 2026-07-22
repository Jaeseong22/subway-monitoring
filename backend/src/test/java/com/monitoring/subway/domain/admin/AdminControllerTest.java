package com.monitoring.subway.domain.admin;

import com.monitoring.subway.config.GlobalExceptionHandler;
import com.monitoring.subway.domain.admin.dto.AdminSummaryDto;
import com.monitoring.subway.domain.admin.dto.RemediationActionDto;
import com.monitoring.subway.domain.auth.AppUser;
import com.monitoring.subway.domain.auth.AuthGuard;
import com.monitoring.subway.domain.auth.UserRole;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * AdminController의 인증 가드와 전역 예외 처리를 검증한다. DB/ES 없이 서비스와
 * AuthGuard를 mock한다. GlobalExceptionHandler가 ResponseStatusException을 올바른
 * 상태코드로 변환하는지도 함께 본다.
 */
@WebMvcTest(AdminController.class)
@Import(GlobalExceptionHandler.class)
class AdminControllerTest {

    @Autowired
    private MockMvc mvc;

    @MockitoBean
    private AdminService adminService;

    @MockitoBean
    private RemediationService remediationService;

    @MockitoBean
    private AuthGuard authGuard;

    private AppUser admin() {
        return AppUser.builder().name("관리자").email("admin@x").role(UserRole.ADMIN).build();
    }

    @Test
    void summary_withoutToken_returns401() throws Exception {
        when(authGuard.requireAdmin(any()))
            .thenThrow(new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다."));

        mvc.perform(get("/api/v1/admin/summary"))
            .andExpect(status().isUnauthorized())
            .andExpect(jsonPath("$.status").value(401))
            .andExpect(jsonPath("$.message").value("로그인이 필요합니다."))
            .andExpect(jsonPath("$.path").value("/api/v1/admin/summary"));
    }

    @Test
    void summary_asNonAdmin_returns403() throws Exception {
        when(authGuard.requireAdmin(any()))
            .thenThrow(new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다."));

        mvc.perform(get("/api/v1/admin/summary").header("Authorization", "Bearer user-token"))
            .andExpect(status().isForbidden())
            .andExpect(jsonPath("$.status").value(403));
    }

    @Test
    void summary_asAdmin_returnsData() throws Exception {
        when(authGuard.requireAdmin(any())).thenReturn(admin());
        when(adminService.getSummary())
            .thenReturn(new AdminSummaryDto("위험", 2, 1, 1, "API 장애", "2026-07-22T00:00:00Z"));

        mvc.perform(get("/api/v1/admin/summary").header("Authorization", "Bearer admin-token"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.systemStatus").value("위험"))
            .andExpect(jsonPath("$.criticalCount").value(1));
    }

    @Test
    void approve_delegatesToService() throws Exception {
        when(authGuard.requireAdmin(any())).thenReturn(admin());
        when(remediationService.approve(eq("a1"), eq("admin@x")))
            .thenReturn(new RemediationActionDto("a1", "APPROVED", "scale_out", "이유", "backend",
                1, 2, "", "", "트래픽 급증", List.of("traffic"), List.of(), List.of(),
                false, false, false));

        mvc.perform(post("/api/v1/admin/remediation/a1/approve").header("Authorization", "Bearer admin"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("APPROVED"));
    }

    @Test
    void approve_alreadyProcessed_returns409() throws Exception {
        when(authGuard.requireAdmin(any())).thenReturn(admin());
        when(remediationService.approve(any(), any()))
            .thenThrow(new ResponseStatusException(HttpStatus.CONFLICT, "이미 처리된 조치입니다."));

        mvc.perform(post("/api/v1/admin/remediation/a1/approve").header("Authorization", "Bearer admin"))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.status").value(409))
            .andExpect(jsonPath("$.message").value("이미 처리된 조치입니다."));
    }
}
