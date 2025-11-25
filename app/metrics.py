"""Prometheus metrics for IMPulse application."""
import time
from contextlib import asynccontextmanager

from prometheus_client import Histogram


@asynccontextmanager
async def measure_metrics(*, messenger_type: str, histogram: Histogram):
    """
    Async context manager to measure elapsed time and increment counters.
    """
    start = time.perf_counter()
    context = {'status_class': 'error'}
    try:
        yield context
    finally:
        duration = time.perf_counter() - start
        status = context.get('status_class', 'error')
        histogram.labels(
            messenger_type=messenger_type,
            status_class=status
        ).observe(duration)


api_response_time_seconds = Histogram(
    'api_response_time_seconds',
    'HTTP response time for messenger API requests',
    ['messenger_type', 'status_class'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')]
)
