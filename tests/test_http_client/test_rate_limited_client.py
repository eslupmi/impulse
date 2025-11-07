import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
from aiohttp import web

from app.http_client import RateLimitedClient
from app.http_client.rate_limited_client import RetryAfterRetry
from tests.utils import FakeTime, create_test_server_url, make_requests_and_close


@pytest_asyncio.fixture
async def mock_server(aiohttp_server):
    """Create a mock HTTP server for testing"""
    request_times = []
    
    def handler(request):
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
            assert abs(client.rate_window - 1.0) < 0.001
            assert client._request_count == 0
    
    async def test_initialization_with_rate_limit(self):
        """Test that client initializes correctly with rate limit"""
        async with RateLimitedClient(rate_limit=20, rate_window=1.0) as client:
            assert client.rate_limit == 20
            assert abs(client.rate_window - 1.0) < 0.001
            assert client._request_count == 0
    
    async def test_requests_without_rate_limit(self, mock_server):
        """Test that requests work normally without rate limit"""
        async with RateLimitedClient() as client:
            url = create_test_server_url(mock_server)
            start_time = time.monotonic()
            
            responses = await make_requests_and_close(client, url, 5)
            
            for response in responses:
                assert response.status == 200
            
            elapsed = time.monotonic() - start_time
            assert elapsed < 0.5
    
    async def test_rate_limiting_enforcement(self, mock_server):
        """Test that rate limiting is enforced correctly"""
        rate_limit = 5
        rate_window = 1.0
        num_requests = rate_limit + 3
        
        async with RateLimitedClient(rate_limit=rate_limit, rate_window=rate_window) as client:
            url = create_test_server_url(mock_server)
            mock_server.request_times.clear()
            
            start_time = time.monotonic()
            responses = await make_requests_and_close(client, url, num_requests)
            elapsed = time.monotonic() - start_time
            
            for response in responses:
                assert response.status == 200
            
            assert elapsed >= rate_window
            assert len(mock_server.request_times) == num_requests
    
    async def test_rate_limit_window_reset(self):
        """Test that rate limit counter resets after idle period"""
        rate_limit = 5
        rate_window = 0.5
        
        with patch('time.monotonic', self.fake_time.monotonic), \
             patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=rate_limit, rate_window=rate_window) as client:
                for _ in range(3):
                    await client._wait_for_rate_limit()
                
                assert client._request_count == 3
                
                self.fake_time.advance(rate_window + 0.1)
                await client._wait_for_rate_limit()
                
                assert client._request_count == 1
    
    async def test_rate_limit_info(self):
        """Test that rate limit info is returned correctly"""
        rate_limit = 10
        rate_window = 2.0
        
        async with RateLimitedClient(rate_limit=rate_limit, rate_window=rate_window) as client:
            info = client.get_rate_limit_info()
            assert info['rate_limit'] == rate_limit
            assert abs(info['rate_window'] - rate_window) < 0.001
            assert info['request_count'] == 0
            assert info['window_start_time'] is None
            assert info['last_request_time'] is None
            
            await client._wait_for_rate_limit()
            
            info = client.get_rate_limit_info()
            assert info['request_count'] == 1
            assert info['window_start_time'] is not None
            assert info['last_request_time'] is not None
    
    async def test_concurrent_requests_with_rate_limit(self, mock_server):
        """Test that concurrent requests respect rate limiting"""
        rate_limit = 5
        rate_window = 0.5
        num_requests = 10
        
        async with RateLimitedClient(rate_limit=rate_limit, rate_window=rate_window) as client:
            url = create_test_server_url(mock_server)
            mock_server.request_times.clear()
            
            start_time = time.monotonic()
            tasks = [asyncio.create_task(client.get(url)) for _ in range(num_requests)]
            responses = await asyncio.gather(*tasks)
            elapsed = time.monotonic() - start_time
            
            for response in responses:
                response.close()
                assert response.status == 200
            
            assert elapsed >= rate_window
            assert len(responses) == num_requests
    
    async def test_http_methods(self, mock_server):
        """Test that all HTTP methods work correctly"""
        async with RateLimitedClient(rate_limit=10, rate_window=1.0) as client:
            url = create_test_server_url(mock_server)
            
            response = await client.get(url)
            assert response.status == 200
            response.close()
            
            response = await client.post(url, json={'test': 'data'})
            assert response.status == 200
            response.close()
    
    async def test_context_manager_closes_client(self):
        """Test that context manager properly closes the client"""
        client = RateLimitedClient(rate_limit=10, rate_window=1.0)
        
        async with client:
            client._initialize_client()
            assert client._client is not None
            assert client._session is not None
        
        assert client._client is None
        assert client._session is None
    
    async def test_manual_close(self):
        """Test that manual close works correctly"""
        client = RateLimitedClient(rate_limit=10, rate_window=1.0)
        client._initialize_client()
        
        assert client._client is not None
        assert client._session is not None
        
        await client.close()
        
        assert client._client is None
        assert client._session is None
    
    async def test_rate_limit_timing_precision(self):
        """Test that rate limiting timing is precise"""
        rate_limit = 3
        rate_window = 0.5
        
        with patch('time.monotonic', self.fake_time.monotonic), \
             patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=rate_limit, rate_window=rate_window) as client:
                request_times = []
                
                for _ in range(rate_limit + 2):
                    await client._wait_for_rate_limit()
                    request_times.append(self.fake_time.monotonic())
                
                for i in range(rate_limit - 1):
                    time_diff = request_times[i + 1] - request_times[i]
                    assert time_diff < 0.1
                
                time_diff = request_times[rate_limit] - request_times[rate_limit - 1]
                assert time_diff >= rate_window * 0.9
    
    async def test_no_rate_limit_no_delays(self):
        """Test that without rate limit, there are no delays"""
        async with RateLimitedClient(rate_limit=None) as client:
            request_times = []
            
            for _ in range(20):
                start = time.monotonic()
                await client._wait_for_rate_limit()
                request_times.append(start)
            
            total_time = request_times[-1] - request_times[0]
            assert total_time < 0.1
    
    async def test_multiple_windows(self):
        """Test that rate limiting works correctly across multiple windows"""
        rate_limit = 3
        rate_window = 0.3
        
        with patch('time.monotonic', self.fake_time.monotonic), \
             patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=rate_limit, rate_window=rate_window) as client:
                for _ in range(rate_limit):
                    await client._wait_for_rate_limit()
                
                assert client._request_count == rate_limit
                
                await client._wait_for_rate_limit()
                assert client._request_count == 1
                
                for _ in range(rate_limit - 1):
                    await client._wait_for_rate_limit()
                
                assert client._request_count == rate_limit
    
    async def test_429_with_retry_after_header(self, aiohttp_server):
        """Test that 429 responses with Retry-After header are handled correctly"""
        call_count = 0
        
        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return web.Response(status=429, headers={'Retry-After': '1'}, body='Too Many Requests')
            return web.json_response({'status': 'ok'})
        
        app = web.Application()
        app.router.add_get('/test', handler)
        server = await aiohttp_server(app)
        
        with patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=10, rate_window=1.0) as client:
                url = create_test_server_url(server)
                response = await client.get(url)
                
                assert response.status == 200
                assert call_count == 2
                assert self.fake_time.current_time >= 1001.0
                
                response.close()
    
    async def test_429_without_retry_after_header(self, aiohttp_server):
        """Test that 429 responses without Retry-After use exponential backoff"""
        call_count = 0
        
        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return web.Response(status=429, body='Too Many Requests')
            return web.json_response({'status': 'ok'})
        
        app = web.Application()
        app.router.add_get('/test', handler)
        server = await aiohttp_server(app)
        
        with patch('asyncio.sleep', self.fake_time.sleep):
            async with RateLimitedClient(rate_limit=10, rate_window=1.0) as client:
                url = create_test_server_url(server)
                response = await client.get(url)
                
                assert response.status == 200
                assert call_count == 2
                
                response.close()
    
    async def test_rate_limit_parameters(self):
        """Test that rate limit parameters are correctly set"""
        async with RateLimitedClient(rate_limit=15, rate_window=2.0) as client:
            assert client.rate_limit == 15
            assert abs(client.rate_window - 2.0) < 0.001
    
    async def test_no_rate_limit_parameters(self):
        """Test that client works without rate limit"""
        async with RateLimitedClient(rate_limit=None, rate_window=1.0) as client:
            assert client.rate_limit is None
            assert abs(client.rate_window - 1.0) < 0.001


class TestRetryAfterRetry:
    """Test cases for RetryAfterRetry policy (synchronous tests)"""
    
    def test_retry_after_respects_max_timeout(self):
        """Test that Retry-After values are capped by max_timeout"""
        retry_policy = RetryAfterRetry(attempts=3, statuses=[429], max_timeout=5.0)
        
        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.headers = {'Retry-After': '100'}
        
        timeout = retry_policy.get_timeout(attempt=1, response=mock_response)
        assert abs(timeout - 5.0) < 0.001
    
    def test_retry_after_with_invalid_value(self):
        """Test that invalid Retry-After values fall back to exponential backoff"""
        retry_policy = RetryAfterRetry(attempts=3, statuses=[429], max_timeout=30.0)
        
        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.headers = {'Retry-After': 'invalid-value'}
        
        timeout = retry_policy.get_timeout(attempt=1, response=mock_response)
        assert timeout > 0

