"""Prometheus metrics for IMPulse application."""
import asyncio
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Optional

import aiohttp
from prometheus_client import (
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST
)
from fastapi.responses import Response

from app.config.config import get_config
from app.queue.queue import AsyncQueue


class MetricsCollector:
    """Singleton class for collecting and exposing Prometheus metrics."""

    _instance: Optional['MetricsCollector'] = None

    def __new__(cls):
        """Create or return existing singleton instance."""
        if cls._instance is None:
            cls._instance = super(MetricsCollector, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.messenger_api_request_duration_seconds = Histogram(
            'impulse_messenger_api_request_duration_seconds',
            'Request duration to messenger API',
            ['messenger', 'status', 'error'],
            buckets=[
                0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')
            ]
        )
        self.status = Gauge(
            'impulse_status',
            'IMPulse instance status (1.0=primary, 0.0=standby)'
        )
        self.queue_latency_seconds = Gauge(
            'impulse_queue_latency_seconds',
            'Last observed delay between scheduled queue task and Prometheus scrape time'
        )

    @classmethod
    def measure_request(cls, func):
        """
        Measure HTTP request duration and track status/errors.
        """
        collector = cls()

        @wraps(func)
        async def wrapper(instance, *args, **kwargs):
            config = get_config()
            messenger_type = config.messenger.type.value

            start = time.perf_counter()
            status = 'no_response'
            error = 'unknown'

            try:
                response = await func(instance, *args, **kwargs)
                status_code = response.status
                status = f'{status_code // 100}xx'
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
                histogram = collector.messenger_api_request_duration_seconds
                histogram.labels(
                    messenger=messenger_type,
                    status=status,
                    error=error
                ).observe(duration)

        return wrapper

    async def update_queue_latency(self, queue: AsyncQueue):
        """
        Update queue latency metric based on first item in queue.

        Args:
            queue: AsyncQueue instance to check for latency
        """
        first_item_datetime = await queue.get_first_item_datetime()

        if first_item_datetime is None:
            self.queue_latency_seconds.set(0.0)
        else:
            now = datetime.now(timezone.utc)
            delay = max(0, (now - first_item_datetime).total_seconds())
            self.queue_latency_seconds.set(delay)

    async def generate_metrics_response(self, queue: AsyncQueue) -> Response:
        """
        Generate Prometheus metrics response.

        Args:
            queue: Optional AsyncQueue instance to update queue latency metric.
                   If None (standby mode), queue latency will be set to 0.0.

        Returns:
            FastAPI Response with metrics content
        """
        await self.update_queue_latency(queue)
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
