package com.monitoring.subway.domain.auth;

import com.fasterxml.jackson.annotation.JsonProperty;

public record GoogleTokenInfo(
    String aud,
    String sub,
    String email,
    String name,
    String picture,
    @JsonProperty("email_verified") String emailVerified
) {
    public boolean isEmailVerified() {
        return "true".equalsIgnoreCase(emailVerified);
    }
}

