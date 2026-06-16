package com.monitoring.subway.logging;

import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.LongAdder;
import org.springframework.stereotype.Component;

@Component
public class RequestTrafficMetrics {

    private final LongAdder requestCount = new LongAdder();
    private final LongAdder errorCount = new LongAdder();
    private final LongAdder totalElapsedMs = new LongAdder();
    private final AtomicInteger inFlightRequests = new AtomicInteger();
    private final AtomicInteger maxConcurrentRequests = new AtomicInteger();
    private final AtomicLong lastSnapshotEpochMs = new AtomicLong(System.currentTimeMillis());

    public void markStart() {
        int current = inFlightRequests.incrementAndGet();
        maxConcurrentRequests.accumulateAndGet(current, Math::max);
    }

    public void markComplete(long elapsedMs, boolean success) {
        requestCount.increment();
        totalElapsedMs.add(Math.max(elapsedMs, 0));
        if (!success) {
            errorCount.increment();
        }
        inFlightRequests.decrementAndGet();
    }

    public Snapshot snapshotAndReset() {
        long now = System.currentTimeMillis();
        long previous = lastSnapshotEpochMs.getAndSet(now);
        double windowSeconds = Math.max(Duration.between(
            Instant.ofEpochMilli(previous),
            Instant.ofEpochMilli(now)
        ).toMillis() / 1000.0, 1.0);

        long requests = requestCount.sumThenReset();
        long errors = errorCount.sumThenReset();
        long elapsed = totalElapsedMs.sumThenReset();
        int currentInFlight = Math.max(inFlightRequests.get(), 0);
        int maxConcurrent = Math.max(maxConcurrentRequests.getAndSet(currentInFlight), currentInFlight);

        return new Snapshot(
            requests,
            errors,
            requests == 0 ? 0.0 : (double) elapsed / requests,
            requests / windowSeconds,
            currentInFlight,
            maxConcurrent,
            windowSeconds
        );
    }

    public record Snapshot(
        long requestCount,
        long errorCount,
        double avgElapsedMs,
        double requestsPerSecond,
        int inFlightRequests,
        int maxConcurrentRequests,
        double windowSeconds
    ) {}
}
