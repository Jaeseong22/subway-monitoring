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
        long startTime = System.currentTimeMillis();
        requestTrafficMetrics.markStart();
        
        // MDC 설정
        MDC.put("event_type", "TRAFFIC");
        MDC.put("event_name", methodName);
        MDC.put("endpoint", endpointName);
        MDC.put("request_id", UUID.randomUUID().toString());
        
        try {
            Object result = joinPoint.proceed();
            long elapsedTime = System.currentTimeMillis() - startTime;
            requestTrafficMetrics.markComplete(elapsedTime, true);
            
            MDC.put("elapsed_ms", String.valueOf(elapsedTime));
            MDC.put("success", "true");
            
            log.info("API request completed successfully.");
            return result;
        } catch (Exception e) {
            long elapsedTime = System.currentTimeMillis() - startTime;
            requestTrafficMetrics.markComplete(elapsedTime, false);
            
            MDC.put("elapsed_ms", String.valueOf(elapsedTime));
            MDC.put("success", "false");
            MDC.put("error_msg", e.getMessage());
            
            log.error("API request failed.", e);
            throw e;
        } finally {
            MDC.clear();
        }
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
        MDC.put("run_id", UUID.randomUUID().toString());
        
        try {
            Object result = joinPoint.proceed();
            long elapsedTime = System.currentTimeMillis() - startTime;
            
            MDC.put("elapsed_ms", String.valueOf(elapsedTime));
            MDC.put("success", "true");
            
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
            MDC.remove("run_id");
            MDC.remove("elapsed_ms");
            MDC.remove("success");
            MDC.remove("error_msg");
            // Do not clear completely here in case it's called within SCHEDULER MDC context
        }
    }
}
