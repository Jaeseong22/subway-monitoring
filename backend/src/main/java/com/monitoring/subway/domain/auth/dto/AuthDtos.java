package com.monitoring.subway.domain.auth.dto;

import com.monitoring.subway.domain.auth.AppUser;

public class AuthDtos {

    public record RegisterRequest(String name, String email, String password) {}

    public record LoginRequest(String email, String password) {}

    public record GoogleLoginRequest(String idToken) {}

    public record UserResponse(
        Long id,
        String name,
        String email,
        String role,
        String provider,
        String profileImageUrl
    ) {
        public static UserResponse from(AppUser user) {
            return new UserResponse(
                user.getId(),
                user.getName(),
                user.getEmail(),
                user.getRole().name(),
                user.getProvider().name(),
                user.getProfileImageUrl()
            );
        }
    }

    public record AuthResponse(String token, UserResponse user) {}
}

