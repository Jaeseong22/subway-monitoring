package com.monitoring.subway.domain.auth;

import com.monitoring.subway.domain.auth.dto.AuthDtos.AuthResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * AuthService의 로그인/회원가입 비즈니스 규칙을 검증한다. 리포지토리는 mock하고
 * PasswordHasher는 실제(순수 함수)를 써서 해시/검증 경로까지 실제로 태운다. DB 불필요.
 */
@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock private AppUserRepository appUserRepository;
    @Mock private AuthSessionRepository authSessionRepository;
    @Mock private WebClient.Builder webClientBuilder;

    private AuthService authService;
    private final PasswordHasher passwordHasher = new PasswordHasher();

    @BeforeEach
    void setUp() {
        authService = new AuthService(appUserRepository, authSessionRepository,
            passwordHasher, webClientBuilder);
        ReflectionTestUtils.setField(authService, "googleClientId", "");
    }

    private AppUser localUser(String email, String rawPassword) {
        return AppUser.builder()
            .name("사용자")
            .email(AppUser.normalizeEmail(email))
            .passwordHash(passwordHasher.hash(rawPassword))
            .role(UserRole.USER)
            .provider(AuthProvider.LOCAL)
            .build();
    }

    @Test
    void login_withCorrectPassword_returnsToken() {
        when(appUserRepository.findByEmail("user@x.com"))
            .thenReturn(Optional.of(localUser("user@x.com", "secret123")));

        AuthResponse response = authService.login("User@X.com", "secret123");  // 대소문자 정규화

        assertThat(response.token()).isNotBlank();
        assertThat(response.user().email()).isEqualTo("user@x.com");
        verify(authSessionRepository).save(any(AuthSession.class));  // 세션 발급됨
    }

    @Test
    void login_withWrongPassword_throwsAndIssuesNoSession() {
        when(appUserRepository.findByEmail("user@x.com"))
            .thenReturn(Optional.of(localUser("user@x.com", "secret123")));

        assertThatThrownBy(() -> authService.login("user@x.com", "wrong"))
            .isInstanceOf(IllegalArgumentException.class);
        verify(authSessionRepository, never()).save(any());
    }

    @Test
    void login_unknownEmail_throwsSameGenericMessage() {
        when(appUserRepository.findByEmail(any())).thenReturn(Optional.empty());

        // 이메일 존재 여부를 노출하지 않도록 오류 메시지가 동일해야 한다.
        assertThatThrownBy(() -> authService.login("nobody@x.com", "whatever"))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("이메일 또는 비밀번호가 올바르지 않습니다.");
    }

    @Test
    void register_duplicateEmail_throws() {
        when(appUserRepository.existsByEmail("dup@x.com")).thenReturn(true);

        assertThatThrownBy(() -> authService.register("이름", "dup@x.com", "password1"))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("이미 가입된 이메일");
        verify(appUserRepository, never()).save(any());
    }

    @Test
    void register_valid_savesUserWithHashedPassword() {
        when(appUserRepository.existsByEmail(any())).thenReturn(false);
        when(appUserRepository.save(any(AppUser.class))).thenAnswer(inv -> inv.getArgument(0));

        AuthResponse response = authService.register("새사용자", "New@X.com", "password1");

        assertThat(response.user().email()).isEqualTo("new@x.com");
        assertThat(response.token()).isNotBlank();
    }

    @Test
    void register_shortPassword_throwsBeforeHitingRepository() {
        assertThatThrownBy(() -> authService.register("이름", "a@x.com", "123"))
            .isInstanceOf(IllegalArgumentException.class);
        verify(appUserRepository, never()).save(any());
    }
}
