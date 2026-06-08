package com.monitoring.subway.domain.auth;

import java.util.Optional;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

@Component
@RequiredArgsConstructor
public class AuthGuard {

    private final AuthSessionRepository authSessionRepository;

    public AppUser requireAdmin(String authorizationHeader) {
        AppUser user = requireUser(authorizationHeader);
        if (user.getRole() != UserRole.ADMIN) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "관리자 권한이 필요합니다.");
        }
        return user;
    }

    public AppUser requireUser(String authorizationHeader) {
        String token = extractBearerToken(authorizationHeader);
        AuthSession session = authSessionRepository.findByToken(token)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다."));
        if (session.isExpired()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인 세션이 만료되었습니다.");
        }
        return session.getUser();
    }

    public Optional<AppUser> findUser(String authorizationHeader) {
        if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
            return Optional.empty();
        }
        String token = authorizationHeader.substring("Bearer ".length()).trim();
        return authSessionRepository.findByToken(token)
            .filter(session -> !session.isExpired())
            .map(AuthSession::getUser);
    }

    private String extractBearerToken(String authorizationHeader) {
        if (authorizationHeader == null || !authorizationHeader.startsWith("Bearer ")) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다.");
        }
        return authorizationHeader.substring("Bearer ".length()).trim();
    }
}
