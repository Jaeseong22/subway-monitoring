package com.monitoring.subway.domain.auth;

import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AppUserRepository extends JpaRepository<AppUser, Long> {
    Optional<AppUser> findByEmail(String email);
    Optional<AppUser> findByGoogleSub(String googleSub);
    boolean existsByEmail(String email);
}

