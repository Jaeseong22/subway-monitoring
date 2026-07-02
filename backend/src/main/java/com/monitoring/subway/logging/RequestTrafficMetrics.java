package com.monitoring.subway.logging;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.LongAdder;
import org.springframework.stereotype.Component;

@Component
public class RequestTrafficMetrics {

    // 창(window)당 지연 표본 상한. p95 계산용이며 메모리 폭증을 막는다.
    private static final int MAX_LATENCY_SAMPLES = 20_000;

    private final LongAdder requestCount = new LongAdder();
    private final LongAdder errorCount = new LongAdder();
    private final LongAdder totalElapsedMs = new LongAdder();
    private final AtomicInteger inFlightRequests = new AtomicInteger();
    private final AtomicInteger maxConcurrentRequests = new AtomicInteger();
    private final AtomicLong lastSnapshotEpochMs = new AtomicLong(System.currentTimeMillis());
    // p95 지연 계산을 위한 최근 응답시간 표본. 스냅샷마다 비운다.
    private final Queue<Long> latencySamples = new ConcurrentLinkedQueue<>();
    private final AtomicInteger latencySampleCount = new AtomicInteger();

    public void markStart() {
        int current = inFlightRequests.incrementAndGet();
        maxConcurrentRequests.accumulateAndGet(current, Math::max);
    }

    public void markComplete(long elapsedMs, boolean success) {
        long clamped = Math.max(elapsedMs, 0);
        requestCount.increment();
        totalElapsedMs.add(clamped);
        if (latencySampleCount.get() < MAX_LATENCY_SAMPLES) {
            latencySamples.offer(clamped);
            latencySampleCount.incrementAndGet();
        }
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
        double p95 = drainAndComputeP95();

        return new Snapshot(
            requests,
            errors,
            requests == 0 ? 0.0 : (double) elapsed / requests,
            p95,
            requests / windowSeconds,
            currentInFlight,
            maxConcurrent,
            windowSeconds
        );
    }

    /** 이번 창의 지연 표본을 비우면서 p95를 계산한다. 표본이 없으면 0. */
    private double drainAndComputeP95() {
        List<Long> samples = new ArrayList<>();
        Long sample;
        while ((sample = latencySamples.poll()) != null) {
            samples.add(sample);
        }
        latencySampleCount.set(0);
        if (samples.isEmpty()) {
            return 0.0;
        }
        Collections.sort(samples);
        // 최근접 순위(nearest-rank) 방식 p95
        int rank = (int) Math.ceil(0.95 * samples.size());
        int index = Math.min(Math.max(rank - 1, 0), samples.size() - 1);
        return samples.get(index);
    }

    public record Snapshot(
        long requestCount,
        long errorCount,
        double avgElapsedMs,
        double p95ElapsedMs,
        double requestsPerSecond,
        int inFlightRequests,
        int maxConcurrentRequests,
        double windowSeconds
    ) {}
}
