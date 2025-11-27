"""Prometheus metrics for IMPulse application."""
import time
from contextlib import asynccontextmanager

from prometheus_client import Gauge, Histogram


@asynccontextmanager
async def measure_metrics(*, messenger: str, histogram: Histogram):
    """
    Async context manager to measure elapsed time and increment counters.
    Yields a mutable context dict:
        context['status'] -> '1xx'|'2xx'|'3xx'|'4xx'|'5xx'|'no_response' (no_response = non-HTTP error)
        context['error']  -> 'none'|'connection_failed'|'timeout'|'unknown'
    """
    start = time.perf_counter()
    context = {'status': 'no_response', 'error': 'unknown'}
    try:
        yield context
    finally:
        duration = time.perf_counter() - start
        status = context.get('status', 'no_response')
        error = context.get('error', 'unknown')
        histogram.labels(
            messenger=messenger,
            status=status,
            error=error
        ).observe(duration)


metrics_messenger_api_request_duration_seconds = Histogram(
    'impulse_messenger_api_request_duration_seconds',
    'Request duration to messenger API',
    ['messenger', 'status', 'error'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')]
)

metrics_status = Gauge(
    'impulse_status',
    'IMPulse instance status (1.0=primary, 0.0=standby)'
)

metrics_queue_latency_seconds = Gauge(
    'impulse_queue_latency_seconds',
    'Delay between scheduled and actual processing time for queue items'
)
