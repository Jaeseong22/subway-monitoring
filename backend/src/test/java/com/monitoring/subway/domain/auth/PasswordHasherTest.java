package com.monitoring.subway.domain.auth;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class PasswordHasherTest {

    private final PasswordHasher hasher = new PasswordHasher();

    @Test
    void hashThenMatchesReturnsTrueForCorrectPassword() {
        String encoded = hasher.hash("s3cret-pw");
        assertTrue(hasher.matches("s3cret-pw", encoded));
    }

    @Test
    void matchesReturnsFalseForWrongPassword() {
        String encoded = hasher.hash("s3cret-pw");
        assertFalse(hasher.matches("wrong-pw", encoded));
    }

    @Test
    void hashUsesRandomSaltSoOutputsDiffer() {
        String first = hasher.hash("same-password");
        String second = hasher.hash("same-password");
        // 소금(salt)이 매번 랜덤이므로 같은 비밀번호라도 인코딩 결과가 달라야 한다.
        assertNotEquals(first, second);
        // 그럼에도 둘 다 원본 비밀번호로 검증되어야 한다.
        assertTrue(hasher.matches("same-password", first));
        assertTrue(hasher.matches("same-password", second));
    }

    @Test
    void encodedHashHasExpectedFormat() {
        String encoded = hasher.hash("pw");
        String[] parts = encoded.split("\\$");
        assertTrue(parts.length == 4, "형식은 pbkdf2$iterations$salt$hash 여야 한다");
        assertTrue("pbkdf2".equals(parts[0]));
        assertTrue(Integer.parseInt(parts[1]) >= 120_000);
    }

    @Test
    void matchesReturnsFalseForNullOrMalformedInput() {
        assertFalse(hasher.matches(null, "whatever"));
        assertFalse(hasher.matches("pw", null));
        assertFalse(hasher.matches("pw", ""));
        assertFalse(hasher.matches("pw", "not-a-valid-hash"));
        assertFalse(hasher.matches("pw", "bcrypt$1$a$b"));
    }
}
