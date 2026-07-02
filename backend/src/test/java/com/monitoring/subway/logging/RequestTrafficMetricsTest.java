package com.monitoring.subway.logging;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class RequestTrafficMetricsTest {

    @Test
    void snapshotAggregatesRequestsAndErrors() {
        RequestTrafficMetrics metrics = new RequestTrafficMetrics();
        metrics.markStart();
        metrics.markComplete(100, true);
        metrics.markStart();
        metrics.markComplete(300, false);

        RequestTrafficMetrics.Snapshot snap = metrics.snapshotAndReset();
        assertEquals(2, snap.requestCount());
        assertEquals(1, snap.errorCount());
        assertEquals(200.0, snap.avgElapsedMs(), 0.001); // (100 + 300) / 2
        assertTrue(snap.requestsPerSecond() >= 0.0);
    }

    @Test
    void snapshotResetsCountersForNextWindow() {
        RequestTrafficMetrics metrics = new RequestTrafficMetrics();
        metrics.markStart();
        metrics.markComplete(50, true);
        metrics.snapshotAndReset();

        RequestTrafficMetrics.Snapshot second = metrics.snapshotAndReset();
        assertEquals(0, second.requestCount());
        assertEquals(0, second.errorCount());
        assertEquals(0.0, second.avgElapsedMs(), 0.001);
    }

    @Test
    void tracksMaxConcurrentRequests() {
        RequestTrafficMetrics metrics = new RequestTrafficMetrics();
        metrics.markStart(); // in-flight 1
        metrics.markStart(); // in-flight 2
        metrics.markStart(); // in-flight 3 (peak)
        metrics.markComplete(10, true); // in-flight 2
        metrics.markComplete(10, true); // in-flight 1
        metrics.markComplete(10, true); // in-flight 0

        RequestTrafficMetrics.Snapshot snap = metrics.snapshotAndReset();
        assertEquals(3, snap.maxConcurrentRequests());
        assertEquals(0, snap.inFlightRequests());
    }

    @Test
    void negativeElapsedIsClampedToZero() {
        RequestTrafficMetrics metrics = new RequestTrafficMetrics();
        metrics.markStart();
        metrics.markComplete(-500, true);
        RequestTrafficMetrics.Snapshot snap = metrics.snapshotAndReset();
        assertEquals(0.0, snap.avgElapsedMs(), 0.001);
    }
}
