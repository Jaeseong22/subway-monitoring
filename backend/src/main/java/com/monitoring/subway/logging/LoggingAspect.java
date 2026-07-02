package com.monitoring.subway.logging;

import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.JoinPoint;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;

import java.util.UUID;

@Slf4j
@Aspect
@Component
public class LoggingAspect {

    private final RequestTrafficMetrics requestTrafficMetrics;

    public LoggingAspect(RequestTrafficMetrics requestTrafficMetrics) {
        this.requestTrafficMetrics = requestTrafficMetrics;
    }

    @Around("execution(* com.monitoring.subway.domain..*Controller.*(..))")
    public Object logTraffic(ProceedingJoinPoint joinPoint) throws Throwable {
        String methodName = joinPoint.getSignature().getName();
        String endpointName = endpointName(joinPoint);
        String requestId = UUID.randomUUID().toString();
        long startTime = System.currentTimeMillis();
        requestTrafficMetrics.markStart();

        // MDC 설정
        applyTrafficContext(methodName, endpointName, requestId);

        try {
            Object result = joinPoint.proceed();
            long elapsedTime = System.currentTimeMillis() - startTime;
            requestTrafficMetrics.markComplete(elapsedTime, true);

            // 감싼 컨트롤러가 자체 finally에서 MDC.clear()를 호출할 수 있으므로,
            // 완료 로그가 TRAFFIC 컨텍스트(event_type/endpoint/request_id)를 잃지 않도록 재설정한다.
            applyTrafficContext(methodName, endpointName, requestId);
            MDC.put("elapsed_ms", String.valueOf(elapsedTime));
            MDC.put("success", "true");

            log.info("API request completed successfully.");
            return result;
        } catch (Exception e) {
            long elapsedTime = System.currentTimeMillis() - startTime;
            requestTrafficMetrics.markComplete(elapsedTime, false);

            applyTrafficContext(methodName, endpointName, requestId);
            MDC.put("elapsed_ms", String.valueOf(elapsedTime));
            MDC.put("success", "false");
            MDC.put("error_msg", e.getMessage());

            log.error("API request failed.", e);
            throw e;
        } finally {
            MDC.clear();
        }
    }

    private void applyTrafficContext(String methodName, String endpointName, String requestId) {
        MDC.put("event_type", "TRAFFIC");
        MDC.put("event_name", methodName);
        MDC.put("endpoint", endpointName);
        MDC.put("request_id", requestId);
    }

    private String endpointName(JoinPoint joinPoint) {
        return joinPoint.getSignature().getDeclaringType().getSimpleName() + "." + joinPoint.getSignature().getName();
    }

    @Around("@annotation(org.springframework.scheduling.annotation.Scheduled)")
    public Object logScheduler(ProceedingJoinPoint joinPoint) throws Throwable {
        String methodName = joinPoint.getSignature().getName();
        long startTime = System.currentTimeMillis();

        // 1. 기존 컨텍스트 백업 (Scheduler 실행 중 다른 것도 섞이지 않게)
        MDC.put("event_type", "SCHEDULER");
        MDC.put("scheduler_name", methodName);
        MDC.put("run_id", UUID.randomUUID().toString());

        try {
            Object result = joinPoint.proceed();
            long elapsedTime = System.currentTimeMillis() - startTime;
            
            MDC.put("duration_ms", String.valueOf(elapsedTime));
            MDC.put("success", "true");
            
            log.info("Scheduler execution completed successfully.");
            return result;
        } catch (Exception e) {
            long elapsedTime = System.currentTimeMillis() - startTime;
            
            MDC.put("duration_ms", String.valueOf(elapsedTime));
            MDC.put("success", "false");
            MDC.put("error_msg", e.getMessage());
            
            log.error("Scheduler execution failed.", e);
            throw e;
        } finally {
            MDC.clear();
        }
    }

    @Around("execution(* com.monitoring.subway.external..*Client.*(..))")
    public Object logApiCollection(ProceedingJoinPoint joinPoint) throws Throwable {
        String methodName = joinPoint.getSignature().getName();
        long startTime = System.currentTimeMillis();
        
        MDC.put("event_type", "API_COLLECTION");
        MDC.put("api_name", methodName);
        MDC.put("endpoint", endpointName(joinPoint));
        MDC.put("run_id", UUID.randomUUID().toString());

        try {
            Object result = joinPoint.proceed();
            long elapsedTime = System.currentTimeMillis() - startTime;

            MDC.put("elapsed_ms", String.valueOf(elapsedTime));
            // 클라이언트가 수집 중 http_status/error_code를 기록했다면 실패로 간주한다.
            MDC.put("success", MDC.get("http_status") == null && MDC.get("error_code") == null ? "true" : "false");

            log.info("External API call completed.");
            return result;
        } catch (Exception e) {
            long elapsedTime = System.currentTimeMillis() - startTime;
            
            MDC.put("elapsed_ms", String.valueOf(elapsedTime));
            MDC.put("success", "false");
            MDC.put("error_msg", e.getMessage());
            
            log.error("External API call failed.", e);
            throw e;
        } finally {
            MDC.remove("event_type");
            MDC.remove("api_name");
            MDC.remove("endpoint");
            MDC.remove("run_id");
            MDC.remove("elapsed_ms");
            MDC.remove("success");
            MDC.remove("error_msg");
            MDC.remove("http_status");
            MDC.remove("error_code");
            // Do not clear completely here in case it's called within SCHEDULER MDC context
        }
    }
}
