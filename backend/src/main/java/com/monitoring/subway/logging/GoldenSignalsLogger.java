package com.monitoring.subway.logging;

import com.sun.management.OperatingSystemMXBean;
import java.lang.management.ManagementFactory;
import java.time.LocalDateTime;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class GoldenSignalsLogger {

    private final RequestTrafficMetrics requestTrafficMetrics;
    private final OperatingSystemMXBean operatingSystemMxBean;

    public GoldenSignalsLogger(RequestTrafficMetrics requestTrafficMetrics) {
        this.requestTrafficMetrics = requestTrafficMetrics;
        this.operatingSystemMxBean = (OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
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
            MDC.put("elapsed_ms", String.format("%.0f", snapshot.avgElapsedMs()));
            MDC.put("avg_elapsed_ms", String.format("%.2f", snapshot.avgElapsedMs()));
            MDC.put("cpu_percent", String.format("%.2f", cpuPercent));
            MDC.put("memory_percent", String.format("%.2f", memoryPercent));
            MDC.put("heap_used_mb", String.valueOf(usedMemory / 1024 / 1024));
            MDC.put("heap_max_mb", String.valueOf(maxMemory / 1024 / 1024));
            MDC.put("queue_depth", String.valueOf(snapshot.maxConcurrentRequests()));
            MDC.put("in_flight_requests", String.valueOf(snapshot.inFlightRequests()));
            MDC.put("max_concurrent_requests", String.valueOf(snapshot.maxConcurrentRequests()));
            MDC.put("active_thread_count", String.valueOf(Thread.activeCount()));
            MDC.put("available_processors", String.valueOf(runtime.availableProcessors()));
            MDC.put("instance_count", "1");
            MDC.put("window_seconds", String.format("%.0f", snapshot.windowSeconds()));
            MDC.put("day_of_week", now.getDayOfWeek().name());
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
