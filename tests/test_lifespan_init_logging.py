import asyncio
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
import pytest

from app.lifespan import _initialize_primary_server


class TestPrimaryServerInitializationLogging:
    @pytest.mark.asyncio
    async def test_logs_initialization_error(self):
        fastapi_app = FastAPI()
        file_lock = Mock()
        file_lock.acquire_lock.return_value = True
        file_lock.release_lock = AsyncMock()

        with patch('app.lifespan.create_main_objects', new=AsyncMock(side_effect=RuntimeError('boom'))), \
                patch('app.lifespan.logger') as mock_logger, \
                patch('app.lifespan.STATUS'):
            success = await _initialize_primary_server(fastapi_app, file_lock)

        assert success is False
        mock_logger.error.assert_called_once_with(
            'Primary server initialization failed', extra={'error': 'boom'},
        )
        mock_logger.exception.assert_not_called()
        file_lock.release_lock.assert_awaited_once()
