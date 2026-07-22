package com.monitoring.subway.config;

import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.stream.Collectors;

/**
 * 전역 예외 처리. 이전에는 AuthController에만 로컬 핸들러가 있어, 나머지 컨트롤러의
 * 예외는 매핑 없이 500 + 기본 에러 포맷(스택트레이스 노출 가능)으로 새어 나갔고
 * 에러 응답 스키마도 컨트롤러마다 제각각이었다. 여기서 통일한다.
 *
 * <p>모든 에러 응답은 {@link ErrorResponse} 형태로 통일된다. 500 응답에는 예외
 * 메시지/스택트레이스를 노출하지 않고(정보 유출 방지) 서버 로그에만 남긴다.
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /** 표준 에러 응답 스키마. */
    public record ErrorResponse(int status, String error, String message, String path, String timestamp) {
        static ErrorResponse of(HttpStatus status, String message, String path) {
            return new ErrorResponse(status.value(), status.getReasonPhrase(), message, path,
                Instant.now().toString());
        }
    }

    /** 컨트롤러/서비스가 명시적으로 던진 상태 예외(401/403/404/409 등). 상태와 사유를 그대로 전달. */
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<ErrorResponse> handleResponseStatus(ResponseStatusException ex,
                                                              HttpServletRequest request) {
        HttpStatus status = HttpStatus.valueOf(ex.getStatusCode().value());
        return ResponseEntity.status(status)
            .body(ErrorResponse.of(status, ex.getReason(), request.getRequestURI()));
    }

    /** 잘못된 입력값 → 400. */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorResponse> handleBadRequest(IllegalArgumentException ex,
                                                          HttpServletRequest request) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
            .body(ErrorResponse.of(HttpStatus.BAD_REQUEST, ex.getMessage(), request.getRequestURI()));
    }

    /** 서버 설정 문제(예: Google client-id 미설정) → 503. */
    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<ErrorResponse> handleServiceUnavailable(IllegalStateException ex,
                                                                  HttpServletRequest request) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
            .body(ErrorResponse.of(HttpStatus.SERVICE_UNAVAILABLE, ex.getMessage(), request.getRequestURI()));
    }

    /** @Valid DTO 검증 실패 → 400. 어떤 필드가 왜 틀렸는지 함께 전달한다. */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex,
                                                          HttpServletRequest request) {
        String detail = ex.getBindingResult().getFieldErrors().stream()
            .map(GlobalExceptionHandler::describeFieldError)
            .collect(Collectors.joining(", "));
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
            .body(ErrorResponse.of(HttpStatus.BAD_REQUEST,
                detail.isBlank() ? "입력값이 유효하지 않습니다." : detail, request.getRequestURI()));
    }

    /** 그 외 모든 예외 → 500. 내부 메시지는 로그에만 남기고 응답에는 노출하지 않는다. */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception ex, HttpServletRequest request) {
        log.error("처리되지 않은 예외: {} {}", request.getMethod(), request.getRequestURI(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(ErrorResponse.of(HttpStatus.INTERNAL_SERVER_ERROR,
                "서버 내부 오류가 발생했습니다.", request.getRequestURI()));
    }

    private static String describeFieldError(FieldError error) {
        return error.getField() + ": " + error.getDefaultMessage();
    }
}
