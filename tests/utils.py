"""
Test utility functions and mock helpers for the test suite.

This module provides reusable utilities for testing, particularly for mocking
aiohttp requests and other async operations.
"""
from unittest.mock import Mock, AsyncMock


class MockContextManager:
    """
    A mock async context manager for testing aiohttp requests.
    
    This utility helps avoid code duplication when mocking aiohttp.ClientSession.post()
    calls that return async context managers.
    """
    
    def __init__(self, response):
        """
        Initialize the mock context manager with a response.
        
        Args:
            response: The mock response object to return when entering the context
        """
        self.response = response
    
    async def __aenter__(self):
        """Return the mock response when entering the context."""
        return self.response
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up when exiting the context."""
        pass


def create_mock_session_with_response(status_code=200):
    """
    Create a mock aiohttp session with a configured response.
    
    Args:
        status_code: HTTP status code for the mock response (default: 200)
        
    Returns:
        tuple: (mock_session, mock_response)
    """
    mock_response = AsyncMock()
    mock_response.status = status_code
    
    mock_session = AsyncMock()
    mock_session.post = Mock(return_value=MockContextManager(mock_response))
    
    return mock_session, mock_response


def create_mock_session_class_with_response(status_code=200):
    """
    Create a mock aiohttp.ClientSession class with a configured response.
    
    Args:
        status_code: HTTP status code for the mock response (default: 200)
        
    Returns:
        tuple: (mock_session_class, mock_session, mock_response)
    """
    mock_response = AsyncMock()
    mock_response.status = status_code
    
    mock_session = AsyncMock()
    mock_session.post = Mock(return_value=MockContextManager(mock_response))
    
    mock_session_class = Mock()
    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    
    return mock_session_class, mock_session, mock_response


def setup_mock_session_class_patch(mock_session_class, status_code=200):
    """
    Setup a mock session class patch with a configured response.
    
    Args:
        mock_session_class: The mock session class from patch
        status_code: HTTP status code for the mock response (default: 200)
        
    Returns:
        tuple: (mock_session, mock_response)
    """
    mock_response = AsyncMock()
    mock_response.status = status_code
    
    mock_session = AsyncMock()
    mock_session.post = Mock(return_value=MockContextManager(mock_response))
    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    
    return mock_session, mock_response
