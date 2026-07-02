package com.monitoring.subway.domain.auth.dto;

import com.monitoring.subway.domain.auth.AppUser;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class AuthDtos {

    public record RegisterRequest(
        @NotBlank @Size(min = 2, max = 50) String name,
        @NotBlank @Email String email,
        @NotBlank @Size(min = 8, max = 100) String password
    ) {}

    public record LoginRequest(
        @NotBlank @Email String email,
        @NotBlank String password
    ) {}

    public record GoogleLoginRequest(
        @NotBlank String idToken
    ) {}

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

