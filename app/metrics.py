"""Prometheus metrics for IMPulse application."""
import asyncio
import time
from datetime import datetime, timezone
from functools import wraps

import aiohttp
from fastapi.responses import Response
from prometheus_client import (
    CollectorRegistry,
    CONTENT_TYPE_LATEST,
    Gauge,
    Histogram,
    generate_latest
)

from app.queue.queue import AsyncQueue

# Create a separate registry for our metrics only
registry = CollectorRegistry()


# Metrics definitions
API_LATENCY = Histogram(
    'impulse_messenger_http_request_duration_seconds',
    'Duration of HTTP requests to messenger API',
    ['status', 'error'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')],
    registry=registry,
)

STATUS = Gauge(
    'impulse_status',
    'IMPulse instance mode (1 - primary, 0 - standby)',
    registry=registry,
)

QUEUE_LATENCY = Gauge(
    'impulse_queue_latency_seconds',
    'Delay in execution of the first queue item',
    registry=registry,
)


def measure_request(func):
    """
    Decorator to measure HTTP request duration and track status/errors.
    """
    @wraps(func)
    async def wrapper(instance, *args, **kwargs):
        start = time.perf_counter()
        status = 'no_response'
        error = 'unknown'

        try:
            response = await func(instance, *args, **kwargs)
            status = f'{response.status // 100}xx'
            error = 'none'
            return response

        except asyncio.TimeoutError:
            error = 'timeout'
            raise

        except aiohttp.ClientConnectorError:
            error = 'connection_failed'
            raise

        finally:
            duration = time.perf_counter() - start
            API_LATENCY.labels(
                status=status,
                error=error
            ).observe(duration)

    return wrapper


async def update_queue_latency(queue: AsyncQueue):
    """
    Update queue latency metric based on first item in queue.

    Args:
        queue: AsyncQueue instance to check for latency
    """
    first_item_datetime = await queue.get_first_item_datetime()

    if first_item_datetime is None:
        QUEUE_LATENCY.set(0.0)
    else:
        now = datetime.now(timezone.utc)
        delay = max(0.0, (now - first_item_datetime).total_seconds())
        QUEUE_LATENCY.set(delay)


async def generate_metrics_response(queue: AsyncQueue) -> Response:
    """
    Generate Prometheus metrics response.

    Args:
        queue: AsyncQueue instance to update queue latency metric.

    Returns:
        FastAPI Response with metrics content
    """
    await update_queue_latency(queue)
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST
    )
