import asyncio
import time
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout, ClientSession, ClientResponse
from aiohttp_retry import ExponentialRetry, RetryClient

from app.http_client.errors import MESSENGER_TRANSPORT_ERRORS
from app.http_client.session import create_client_session
from app.logging import logger
from app.logging_context import messenger_init_log_fields, redact_messenger_url, transport_failure_fields
from app.metrics import measure_request


class RetryAfterRetry(ExponentialRetry):
    """
    Custom retry policy that respects the Retry-After header for 429 responses.
    
    For 429 (Too Many Requests) responses, uses the Retry-After header value
    if present. Otherwise, falls back to exponential backoff for other errors.
    """
    
    def get_timeout(
        self,
        attempt: int,
        response: Optional[ClientResponse] = None
    ) -> float:
        """
        Calculate timeout before next retry attempt.
        
        For 429 responses, checks the Retry-After header and uses that value.
        For other errors, uses exponential backoff.
        
        Args:
            attempt: Current attempt number (1-based)
            response: The response object (if available)
            
        Returns:
            Timeout in seconds before next retry
        """
        if response is not None and response.status == 429:
            retry_after = response.headers.get('Retry-After')
            
            if retry_after:
                try:
                    wait_time = float(retry_after)
                    logger.warning(
                        f"Rate limit hit (429), respecting Retry-After: {wait_time}s"
                    )
                    return min(wait_time, self._max_timeout)
                except ValueError:
                    logger.warning(
                        "Rate limit hit (429) with date-format Retry-After header, "
                        "using exponential backoff"
                    )
        
        return super().get_timeout(attempt, response)


class RateLimitedClient:
    """
    HTTP client with built-in rate limiting.
    
    This client tracks the number of requests made within a time window and
    automatically waits when the rate limit is about to be exceeded. If the API
    is idle for the rate_window duration, the counter resets.
    
    Args:
        rate_limit: Maximum number of requests allowed per rate_window period (None = no limit)
        rate_window: Time window in seconds for the rate limit (default: 1.0)
        retry_attempts: Number of retry attempts for failed requests (default: 3)
        timeout: Request timeout in seconds (default: 30.0)
        connector_limit: Total connection limit (default: 100)
        connector_limit_per_host: Connection limit per host (default: 30)
    """
    
    def __init__(
        self,
        rate_limit: Optional[int] = None,
        rate_window: float = 1.0,
        retry_attempts: int = 3,
        timeout: float = 30.0,
        connector_limit: int = 100,
        connector_limit_per_host: int = 30
    ):
        self.rate_limit = rate_limit
        self.rate_window = rate_window
        
        # Rate limiting state
        self._request_count = 0
        self._window_start_time = None
        self._last_request_time = None
        self._lock = asyncio.Lock()
        
        # HTTP client configuration
        self._retry_attempts = retry_attempts
        self._timeout = timeout
        self._connector_limit = connector_limit
        self._connector_limit_per_host = connector_limit_per_host
        
        # HTTP client (will be initialized in async context)
        self._client: Optional[RetryClient] = None
        self._session: Optional[ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.initialize_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.close()
            self._client = None
            self._session = None
    
    async def delete(self, url: str, **kwargs):
        """Make a DELETE request with rate limiting"""
        return await self.request('DELETE', url, **kwargs)
    
    async def get(self, url: str, **kwargs):
        """Make a GET request with rate limiting"""
        return await self.request('GET', url, **kwargs)
    
    def get_rate_limit_info(self) -> dict:
        """
        Get current rate limit status information.
        
        Returns:
            dict with keys:
                - rate_limit: Maximum requests per window
                - rate_window: Window duration in seconds
                - request_count: Current requests in window
                - window_start_time: Start time of current window
                - last_request_time: Time of last request
        """
        return {
            'rate_limit': self.rate_limit,
            'rate_window': self.rate_window,
            'request_count': self._request_count,
            'window_start_time': self._window_start_time,
            'last_request_time': self._last_request_time
        }
    
    async def head(self, url: str, **kwargs):
        """Make a HEAD request with rate limiting"""
        return await self.request('HEAD', url, **kwargs)
    
    def initialize_client(self):
        """Initialize the HTTP client if not already initialized"""
        if self._client is not None:
            return
        
        retry_options = RetryAfterRetry(
            attempts=self._retry_attempts,
            statuses={429, 500, 502, 503, 504},
            exceptions={aiohttp.ClientError, aiohttp.ServerTimeoutError},
            max_timeout=self._timeout
        )
        
        timeout = ClientTimeout(total=self._timeout)
        connector = aiohttp.TCPConnector(
            limit=self._connector_limit,
            limit_per_host=self._connector_limit_per_host
        )
        
        self._session = create_client_session(
            timeout=timeout,
            connector=connector,
            raise_for_status=False,
        )
        
        self._client = RetryClient(
            client_session=self._session,
            retry_options=retry_options
        )
    
    async def options(self, url: str, **kwargs):
        """Make an OPTIONS request with rate limiting"""
        return await self.request('OPTIONS', url, **kwargs)
    
    async def patch(self, url: str, **kwargs):
        """Make a PATCH request with rate limiting"""
        return await self.request('PATCH', url, **kwargs)
    
    async def post(self, url: str, **kwargs):
        """Make a POST request with rate limiting"""
        return await self.request('POST', url, **kwargs)
    
    async def put(self, url: str, **kwargs):
        """Make a PUT request with rate limiting"""
        return await self.request('PUT', url, **kwargs)
    
    @measure_request
    async def request(self, method: str, url: str, **kwargs):
        """
        Make an HTTP request with rate limiting and metrics tracking.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Request URL
            **kwargs: Additional arguments to pass to aiohttp

        Returns:
            aiohttp.ClientResponse
        """
        self.initialize_client()
        await self._wait_for_rate_limit()
        try:
            return await self._client.request(method, url, **kwargs)
        except MESSENGER_TRANSPORT_ERRORS as exc:
            logger.error(
                "Messenger is not responding",
                extra={
                    'method': method,
                    'url': redact_messenger_url(url),
                    **transport_failure_fields(exc),
                    **messenger_init_log_fields(),
                },
            )
            raise
    
    async def _wait_for_rate_limit(self):
        """
        Check rate limit and wait if necessary.
        
        This method:
        1. Resets the counter if idle for rate_window duration
        2. Waits if the rate limit has been reached within the current window
        3. Updates request tracking state
        """
        if self.rate_limit is None:
            return
        
        async with self._lock:
            current_time = time.monotonic()
            
            if self._last_request_time is not None:
                idle_duration = current_time - self._last_request_time
                if idle_duration >= self.rate_window:
                    self._request_count = 0
                    self._window_start_time = None
            
            if self._window_start_time is None:
                self._window_start_time = current_time
                self._request_count = 0
            
            time_since_window_start = current_time - self._window_start_time
            
            if self._request_count >= self.rate_limit:
                if time_since_window_start < self.rate_window:
                    wait_duration = self.rate_window - time_since_window_start
                    logger.warning(
                        f"Rate limit reached ({self._request_count}/{self.rate_limit}), "
                        f"waiting {wait_duration:.2f}s"
                    )
                    await asyncio.sleep(wait_duration)
                
                self._window_start_time = time.monotonic()
                self._request_count = 0

            self._request_count += 1
            self._last_request_time = time.monotonic()
