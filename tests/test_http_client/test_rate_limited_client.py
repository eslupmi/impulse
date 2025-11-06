import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
import pytest_asyncio
import aiohttp
from aiohttp import web

from app.http_client import RateLimitedClient
from app.http_client.rate_limited_client import RetryAfterRetry


class FakeTime:
    """Helper class to simulate time progression without actual waiting"""
    def __init__(self):
        self.current_time = 1000.0
    
    def monotonic(self):
        return self.current_time
    
    def advance(self, seconds):
        self.current_time += seconds
    
    async def sleep(self, seconds):
        """Simulate asyncio.sleep by advancing time"""
        self.advance(seconds)


@pytest_asyncio.fixture
async def mock_server(aiohttp_server):
    """Create a mock HTTP server for testing"""
    request_times = []
    
    async def handler(request):
        request_times.append(time.monotonic())
        return web.json_response({'status': 'ok'})
    
    app = web.Application()
    app.router.add_get('/test', handler)
    app.router.add_post('/test', handler)
    
    server = await aiohttp_server(app)
    server.request_times = request_times
    return server


@pytest.mark.asyncio
class TestRateLimitedClient:
    
    @pytest.fixture(autouse=True)
    def setup_fake_time(self):
        """Setup fake time for all tests to speed them up"""
        self.fake_time = FakeTime()
    
    async def test_initialization_without_rate_limit(self):
        """Test that client initializes correctly without rate limit"""
        async with RateLimitedClient() as client:
            assert client.rate_limit is None
            assert client.wait_time == 1.0
            assert client._request_count == 0
    
    async def test_initialization_with_rate_limit(self):
        """Test that client initializes correctly with rate limit"""
        async with RateLimitedClient(rate_limit=20, wait_time=1.0) as client:
            assert client.rate_limit == 20
            assert client.wait_time == 1.0
            assert client._request_count == 0
    
    async def test_requests_without_rate_limit(self, mock_server):
        """Test that requests work normally without rate limit"""
        async with RateLimitedClient() as client:
            url = f'http://{mock_server.host}:{mock_server.port}/test'
            
            # Make multiple requests quickly
            start_time = time.monotonic()
            responses = []
            for _ in range(5):
                response = await client.get(url)
                responses.append(response)
                assert response.status == 200
            
            # Close all responses
            for response in responses:
                response.close()
            
            # Should complete quickly without delays
            elapsed = time.monotonic() - start_time
            assert elapsed < 0.5  # Should be very fast without rate limiting
    
    async def test_rate_limiting_enforcement(self, mock_server):
        """Test that rate limiting is enforced correctly"""
        rate_limit = 5
        wait_time = 1.0
        
        async with RateLimitedClient(rate_limit=rate_limit, wait_time=wait_time) as client:
            url = f'http://{mock_server.host}:{mock_server.port}/test'
            
            # Clear any previous request times
            mock_server.request_times.clear()
            
            # Make more requests than the rate limit
            num_requests = rate_limit + 3
            start_time = time.monotonic()
            
            responses = []
            for _ in range(num_requests):
                response = await client.get(url)
                responses.append(response)
                assert response.status == 200
            
            # Close all responses
            for response in responses:
                response.close()
            
            elapsed = time.monotonic() - start_time
            
            # Should take at least wait_time due to rate limiting
            assert elapsed >= wait_time
            
            # Check that first rate_limit requests were fast
            # and subsequent requests were delayed
            assert len(mock_server.request_times) == num_requests
    
    async def test_rate_limit_window_reset(self):
        """Test that rate limit counter resets after idle period"""
        rate_limit = 5
        wait_time = 0.5
        
        with patch('time.monotonic', self.fake_time.monotonic), \
             patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=rate_limit, wait_time=wait_time) as client:
                # Make some requests
                for _ in range(3):
                    await client._wait_for_rate_limit()
                
                assert client._request_count == 3
                
                # Simulate waiting for the idle period to expire
                self.fake_time.advance(wait_time + 0.1)
                
                # Make another request - counter should be reset
                await client._wait_for_rate_limit()
                
                # Counter should be 1 after reset
                assert client._request_count == 1
    
    async def test_rate_limit_info(self):
        """Test that rate limit info is returned correctly"""
        rate_limit = 10
        wait_time = 2.0
        
        async with RateLimitedClient(rate_limit=rate_limit, wait_time=wait_time) as client:
            info = client.get_rate_limit_info()
            
            assert info['rate_limit'] == rate_limit
            assert info['wait_time'] == wait_time
            assert info['request_count'] == 0
            assert info['window_start_time'] is None
            assert info['last_request_time'] is None
            
            # Make a request
            await client._wait_for_rate_limit()
            
            info = client.get_rate_limit_info()
            assert info['request_count'] == 1
            assert info['window_start_time'] is not None
            assert info['last_request_time'] is not None
    
    async def test_concurrent_requests_with_rate_limit(self, mock_server):
        """Test that concurrent requests respect rate limiting"""
        rate_limit = 5
        wait_time = 0.5
        
        async with RateLimitedClient(rate_limit=rate_limit, wait_time=wait_time) as client:
            url = f'http://{mock_server.host}:{mock_server.port}/test'
            mock_server.request_times.clear()
            
            # Launch concurrent requests
            num_requests = 10
            start_time = time.monotonic()
            
            tasks = []
            for _ in range(num_requests):
                task = asyncio.create_task(client.get(url))
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks)
            
            # Close all responses
            for response in responses:
                response.close()
            
            elapsed = time.monotonic() - start_time
            
            # Should take at least wait_time due to hitting the rate limit
            assert elapsed >= wait_time
            
            # All requests should succeed
            assert len(responses) == num_requests
            for response in responses:
                assert response.status == 200
    
    async def test_http_methods(self, mock_server):
        """Test that all HTTP methods work correctly"""
        async with RateLimitedClient(rate_limit=10, wait_time=1.0) as client:
            url = f'http://{mock_server.host}:{mock_server.port}/test'
            
            # Test GET
            response = await client.get(url)
            assert response.status == 200
            response.close()
            
            # Test POST
            response = await client.post(url, json={'test': 'data'})
            assert response.status == 200
            response.close()
    
    async def test_context_manager_closes_client(self):
        """Test that context manager properly closes the client"""
        client = RateLimitedClient(rate_limit=10, wait_time=1.0)
        
        async with client:
            await client._initialize_client()
            assert client._client is not None
            assert client._session is not None
        
        # After exiting context, client should be closed
        assert client._client is None
        assert client._session is None
    
    async def test_manual_close(self):
        """Test that manual close works correctly"""
        client = RateLimitedClient(rate_limit=10, wait_time=1.0)
        await client._initialize_client()
        
        assert client._client is not None
        assert client._session is not None
        
        await client.close()
        
        assert client._client is None
        assert client._session is None
    
    async def test_rate_limit_timing_precision(self):
        """Test that rate limiting timing is precise"""
        rate_limit = 3
        wait_time = 0.5
        
        with patch('time.monotonic', self.fake_time.monotonic), \
             patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=rate_limit, wait_time=wait_time) as client:
                request_times = []
                
                # Make more requests than the limit
                for _ in range(rate_limit + 2):
                    await client._wait_for_rate_limit()
                    request_times.append(self.fake_time.monotonic())
                
                # First rate_limit requests should be fast
                for i in range(rate_limit - 1):
                    time_diff = request_times[i + 1] - request_times[i]
                    assert time_diff < 0.1  # Should be very fast
                
                # After hitting the limit, there should be a wait_time delay
                time_diff = request_times[rate_limit] - request_times[rate_limit - 1]
                assert time_diff >= wait_time * 0.9  # Allow 10% tolerance
    
    async def test_no_rate_limit_no_delays(self):
        """Test that without rate limit, there are no delays"""
        async with RateLimitedClient(rate_limit=None) as client:
            request_times = []
            
            # Make many requests
            for _ in range(20):
                start = time.monotonic()
                await client._wait_for_rate_limit()
                request_times.append(start)
            
            # All requests should be very fast
            total_time = request_times[-1] - request_times[0]
            assert total_time < 0.1  # Should complete in less than 100ms
    
    async def test_multiple_windows(self):
        """Test that rate limiting works correctly across multiple windows"""
        rate_limit = 3
        wait_time = 0.3
        
        with patch('time.monotonic', self.fake_time.monotonic), \
             patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=rate_limit, wait_time=wait_time) as client:
                # First window
                for _ in range(rate_limit):
                    await client._wait_for_rate_limit()
                
                first_window_count = client._request_count
                assert first_window_count == rate_limit
                
                # This should trigger a wait and start a new window
                await client._wait_for_rate_limit()
                
                # Should be in a new window with count = 1
                assert client._request_count == 1
                
                # Make more requests in the new window
                for _ in range(rate_limit - 1):
                    await client._wait_for_rate_limit()
                
                assert client._request_count == rate_limit
    
    async def test_429_with_retry_after_header(self, aiohttp_server):
        """Test that 429 responses with Retry-After header are handled correctly"""
        call_count = 0
        
        async def handler(request):
            nonlocal call_count
            call_count += 1
            
            # First request fails with 429 and Retry-After: 1
            if call_count == 1:
                return web.Response(
                    status=429,
                    headers={'Retry-After': '1'},
                    body='Too Many Requests'
                )
            # Second request succeeds
            return web.json_response({'status': 'ok'})
        
        app = web.Application()
        app.router.add_get('/test', handler)
        server = await aiohttp_server(app)
        
        with patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=10, wait_time=1.0) as client:
                url = f'http://{server.host}:{server.port}/test'
                
                # This should fail with 429, wait 1 second (from Retry-After), then succeed
                response = await client.get(url)
                
                assert response.status == 200
                assert call_count == 2  # Should have retried once
                # Check that fake time advanced by approximately 1 second
                assert self.fake_time.current_time >= 1001.0
                
                response.close()
    
    async def test_429_without_retry_after_header(self, aiohttp_server):
        """Test that 429 responses without Retry-After use exponential backoff"""
        call_count = 0
        
        async def handler(request):
            nonlocal call_count
            call_count += 1
            
            # First request fails with 429, no Retry-After header
            if call_count == 1:
                return web.Response(status=429, body='Too Many Requests')
            # Second request succeeds
            return web.json_response({'status': 'ok'})
        
        app = web.Application()
        app.router.add_get('/test', handler)
        server = await aiohttp_server(app)
        
        with patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=10, wait_time=1.0) as client:
                url = f'http://{server.host}:{server.port}/test'
                
                # This should fail with 429, use exponential backoff, then succeed
                response = await client.get(url)
                
                assert response.status == 200
                assert call_count == 2  # Should have retried once
                
                response.close()
    
    async def test_retry_after_respects_max_timeout(self):
        """Test that Retry-After values are capped by max_timeout"""
        retry_policy = RetryAfterRetry(
            attempts=3,
            statuses=[429],
            max_timeout=5.0  # Cap at 5 seconds
        )
        
        # Create a mock response with Retry-After: 100 (too long)
        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.headers = {'Retry-After': '100'}
        
        timeout = retry_policy.get_timeout(attempt=1, response=mock_response)
        
        # Should be capped at max_timeout
        assert timeout == 5.0
    
    async def test_retry_after_with_invalid_value(self):
        """Test that invalid Retry-After values fall back to exponential backoff"""
        retry_policy = RetryAfterRetry(
            attempts=3,
            statuses=[429],
            max_timeout=30.0
        )
        
        # Create a mock response with invalid Retry-After
        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.headers = {'Retry-After': 'invalid-value'}
        
        timeout = retry_policy.get_timeout(attempt=1, response=mock_response)
        
        # Should fall back to exponential backoff (non-zero)
        assert timeout > 0

