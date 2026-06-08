package com.monitoring.subway.domain.auth;

import com.monitoring.subway.domain.auth.dto.AuthDtos.AuthResponse;
import com.monitoring.subway.domain.auth.dto.AuthDtos.UserResponse;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Base64;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;

@Service
@RequiredArgsConstructor
public class AuthService {

    private static final SecureRandom RANDOM = new SecureRandom();

    private final AppUserRepository appUserRepository;
    private final AuthSessionRepository authSessionRepository;
    private final PasswordHasher passwordHasher;
    private final WebClient.Builder webClientBuilder;

    @Value("${google.oauth.client-id:}")
    private String googleClientId;

    @Transactional
    public AuthResponse register(String name, String email, String password) {
        String normalizedEmail = AppUser.normalizeEmail(email);
        validateLocalUserInput(name, normalizedEmail, password);
        if (appUserRepository.existsByEmail(normalizedEmail)) {
            throw new IllegalArgumentException("이미 가입된 이메일입니다.");
        }

        AppUser user = AppUser.builder()
            .name(name.trim())
            .email(normalizedEmail)
            .passwordHash(passwordHasher.hash(password))
            .role(UserRole.USER)
            .provider(AuthProvider.LOCAL)
            .build();
        user.markLogin();
        return toAuthResponse(appUserRepository.save(user));
    }

    @Transactional
    public AuthResponse login(String email, String password) {
        String normalizedEmail = AppUser.normalizeEmail(email);
        AppUser user = appUserRepository.findByEmail(normalizedEmail)
            .orElseThrow(() -> new IllegalArgumentException("이메일 또는 비밀번호가 올바르지 않습니다."));
        if (!passwordHasher.matches(password, user.getPasswordHash())) {
            throw new IllegalArgumentException("이메일 또는 비밀번호가 올바르지 않습니다.");
        }
        user.markLogin();
        return toAuthResponse(user);
    }

    @Transactional
    public AuthResponse loginWithGoogle(String idToken) {
        if (googleClientId == null || googleClientId.isBlank()) {
            throw new IllegalStateException("Google OAuth client ID가 설정되지 않았습니다.");
        }
        if (idToken == null || idToken.isBlank()) {
            throw new IllegalArgumentException("Google ID 토큰이 비어 있습니다.");
        }

        GoogleTokenInfo tokenInfo = webClientBuilder.build()
            .get()
            .uri("https://oauth2.googleapis.com/tokeninfo?id_token={idToken}", idToken)
            .retrieve()
            .bodyToMono(GoogleTokenInfo.class)
            .block();

        if (tokenInfo == null || !googleClientId.equals(tokenInfo.aud()) || !tokenInfo.isEmailVerified()) {
            throw new IllegalArgumentException("Google 인증 정보를 확인할 수 없습니다.");
        }

        String normalizedEmail = AppUser.normalizeEmail(tokenInfo.email());
        AppUser user = appUserRepository.findByGoogleSub(tokenInfo.sub())
            .or(() -> appUserRepository.findByEmail(normalizedEmail))
            .map(existing -> {
                if (existing.getGoogleSub() == null || existing.getGoogleSub().isBlank()) {
                    existing.linkGoogle(tokenInfo.sub(), tokenInfo.picture());
                }
                return existing;
            })
            .orElseGet(() -> appUserRepository.save(AppUser.builder()
                .name(tokenInfo.name() == null || tokenInfo.name().isBlank() ? normalizedEmail : tokenInfo.name())
                .email(normalizedEmail)
                .googleSub(tokenInfo.sub())
                .provider(AuthProvider.GOOGLE)
                .role(UserRole.USER)
                .profileImageUrl(tokenInfo.picture())
                .build()));

        user.markLogin();
        return toAuthResponse(user);
    }

    private void validateLocalUserInput(String name, String email, String password) {
        if (name == null || name.trim().length() < 2) {
            throw new IllegalArgumentException("이름은 2자 이상 입력해주세요.");
        }
        if (email == null || !email.contains("@")) {
            throw new IllegalArgumentException("올바른 이메일을 입력해주세요.");
        }
        if (password == null || password.length() < 8) {
            throw new IllegalArgumentException("비밀번호는 8자 이상 입력해주세요.");
        }
    }

    private AuthResponse toAuthResponse(AppUser user) {
        String token = generateSessionToken();
        authSessionRepository.save(AuthSession.builder()
            .token(token)
            .user(user)
            .expiresAt(LocalDateTime.now().plusDays(7))
            .build());
        return new AuthResponse(token, UserResponse.from(user));
    }

    private String generateSessionToken() {
        byte[] bytes = new byte[32];
        RANDOM.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
