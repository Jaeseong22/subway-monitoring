package com.monitoring.subway.logging;

import com.sun.management.OperatingSystemMXBean;
import java.lang.management.ManagementFactory;
import java.net.InetAddress;
import java.time.LocalDateTime;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class GoldenSignalsLogger {

    private final RequestTrafficMetrics requestTrafficMetrics;
    private final OperatingSystemMXBean operatingSystemMxBean;
    /**
     * 이 프로세스의 식별자. 여러 인스턴스를 띄우면 각자 자신의 지표를 남기므로,
     * 이상탐지 쪽에서 창 내 서로 다른 instance_id 개수를 세어 실제 가동 인스턴스 수를 구한다.
     * (예전에는 instance_count를 "1"로 하드코딩해 확장 시 지표가 왜곡됐다.)
     */
    private final String instanceId;
    /**
     * 이 프로세스의 역할. 수집 전용 프로세스(collector)는 로드밸런서 뒤에 있지 않으므로
     * 자동 확장 판단에서 API 인스턴스 수에 포함되면 안 된다.
     */
    private final String instanceRole;

    public GoldenSignalsLogger(RequestTrafficMetrics requestTrafficMetrics,
                               @Value("${app.scheduler.enabled:true}") boolean schedulerEnabled) {
        this.requestTrafficMetrics = requestTrafficMetrics;
        this.operatingSystemMxBean = (OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
        this.instanceId = resolveInstanceId();
        this.instanceRole = schedulerEnabled ? "collector" : "api";
    }

    private static String resolveInstanceId() {
        String configured = System.getenv("INSTANCE_ID");
        if (configured != null && !configured.isBlank()) {
            return configured;
        }
        try {
            // 컨테이너에서는 호스트명이 컨테이너 ID이므로 인스턴스 구분자로 충분하다.
            return InetAddress.getLocalHost().getHostName();
        } catch (Exception e) {
            return "unknown";
        }
    }

    @Scheduled(fixedRateString = "${monitoring.golden-signals.interval-ms:60000}")
    public void logGoldenSignals() {
        Map<String, String> previousMdc = MDC.getCopyOfContextMap();
        RequestTrafficMetrics.Snapshot snapshot = requestTrafficMetrics.snapshotAndReset();
        Runtime runtime = Runtime.getRuntime();
        long maxMemory = runtime.maxMemory();
        long usedMemory = runtime.totalMemory() - runtime.freeMemory();
        double memoryPercent = maxMemory <= 0 ? 0.0 : (double) usedMemory / maxMemory * 100.0;
        double cpuPercent = normalizeCpuPercent(operatingSystemMxBean.getProcessCpuLoad());
        LocalDateTime now = LocalDateTime.now();

        try {
            MDC.put("event_type", "TRAFFIC");
            MDC.put("event_name", "golden_signals_summary");
            MDC.put("success", "true");
            MDC.put("request_count", String.valueOf(snapshot.requestCount()));
            MDC.put("requests_per_second", String.format("%.2f", snapshot.requestsPerSecond()));
            MDC.put("error_count", String.valueOf(snapshot.errorCount()));
            MDC.put("error_rate", String.format("%.4f", snapshot.requestCount() == 0 ? 0.0 : (double) snapshot.errorCount() / snapshot.requestCount()));
            MDC.put("avg_elapsed_ms", String.format("%.2f", snapshot.avgElapsedMs()));
            MDC.put("p95_elapsed_ms", String.format("%.0f", snapshot.p95ElapsedMs()));
            MDC.put("cpu_percent", String.format("%.2f", cpuPercent));
            MDC.put("memory_percent", String.format("%.2f", memoryPercent));
            MDC.put("heap_used_mb", String.valueOf(usedMemory / 1024 / 1024));
            MDC.put("heap_max_mb", String.valueOf(maxMemory / 1024 / 1024));
            MDC.put("queue_depth", String.valueOf(snapshot.maxConcurrentRequests()));
            MDC.put("in_flight_requests", String.valueOf(snapshot.inFlightRequests()));
            MDC.put("max_concurrent_requests", String.valueOf(snapshot.maxConcurrentRequests()));
            MDC.put("active_thread_count", String.valueOf(Thread.activeCount()));
            MDC.put("available_processors", String.valueOf(runtime.availableProcessors()));
            MDC.put("instance_id", instanceId);
            MDC.put("instance_role", instanceRole);
            MDC.put("window_seconds", String.format("%.0f", snapshot.windowSeconds()));
            MDC.put("day_of_week", now.getDayOfWeek().name());
            MDC.put("is_weekend", String.valueOf(now.getDayOfWeek().getValue() >= 6));
            MDC.put("hour_of_day", String.valueOf(now.getHour()));

            log.info("Golden signals summary collected.");
        } finally {
            restoreMdc(previousMdc);
        }
    }

    private double normalizeCpuPercent(double processCpuLoad) {
        if (processCpuLoad < 0) {
            return 0.0;
        }
        return processCpuLoad * 100.0;
    }

    private void restoreMdc(Map<String, String> previousMdc) {
        if (previousMdc == null) {
            MDC.clear();
            return;
        }
        MDC.setContextMap(previousMdc);
    }
}
