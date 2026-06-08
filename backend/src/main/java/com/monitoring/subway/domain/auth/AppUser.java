package com.monitoring.subway.domain.auth;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "app_user")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AppUser {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 120)
    private String email;

    @Column(nullable = false, length = 80)
    private String name;

    @Column(name = "password_hash", length = 220)
    private String passwordHash;

    @Column(name = "google_sub", unique = true, length = 120)
    private String googleSub;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private UserRole role;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private AuthProvider provider;

    @Column(name = "profile_image_url", length = 500)
    private String profileImageUrl;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Column(name = "last_login_at")
    private LocalDateTime lastLoginAt;

    @Builder
    public AppUser(
        String email,
        String name,
        String passwordHash,
        String googleSub,
        UserRole role,
        AuthProvider provider,
        String profileImageUrl
    ) {
        this.email = normalizeEmail(email);
        this.name = name;
        this.passwordHash = passwordHash;
        this.googleSub = googleSub;
        this.role = role == null ? UserRole.USER : role;
        this.provider = provider == null ? AuthProvider.LOCAL : provider;
        this.profileImageUrl = profileImageUrl;
        this.createdAt = LocalDateTime.now();
    }

    public void markLogin() {
        this.lastLoginAt = LocalDateTime.now();
    }

    public void linkGoogle(String googleSub, String profileImageUrl) {
        this.googleSub = googleSub;
        this.provider = AuthProvider.GOOGLE;
        this.profileImageUrl = profileImageUrl;
    }

    public static String normalizeEmail(String email) {
        return email == null ? "" : email.trim().toLowerCase();
    }
}

