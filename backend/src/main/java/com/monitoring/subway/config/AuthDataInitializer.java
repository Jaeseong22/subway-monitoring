package com.monitoring.subway.config;

import com.monitoring.subway.domain.auth.AppUser;
import com.monitoring.subway.domain.auth.AppUserRepository;
import com.monitoring.subway.domain.auth.AuthProvider;
import com.monitoring.subway.domain.auth.PasswordHasher;
import com.monitoring.subway.domain.auth.UserRole;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
@RequiredArgsConstructor
public class AuthDataInitializer implements CommandLineRunner {

    private final AppUserRepository appUserRepository;
    private final PasswordHasher passwordHasher;

    @Value("${app.admin.email:}")
    private String adminEmail;

    @Value("${app.admin.password:}")
    private String adminPassword;

    @Value("${app.admin.name:관리자}")
    private String adminName;

    @Override
    @Transactional
    public void run(String... args) {
        if (adminEmail == null || adminEmail.isBlank() || adminPassword == null || adminPassword.isBlank()) {
            return;
        }

        String normalizedEmail = AppUser.normalizeEmail(adminEmail);
        if (appUserRepository.existsByEmail(normalizedEmail)) {
            return;
        }

        appUserRepository.save(AppUser.builder()
            .name(adminName)
            .email(normalizedEmail)
            .passwordHash(passwordHasher.hash(adminPassword))
            .provider(AuthProvider.LOCAL)
            .role(UserRole.ADMIN)
            .build());
    }
}
