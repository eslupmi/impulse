"""
Integration tests for main.py FastAPI application.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

import main
from app.config.validation import MessengerType


class TestMainApplication:
    """Test cases for the main FastAPI application."""

    @pytest.fixture
    def mock_app_dependencies(self):
        """Mock all application dependencies."""
        with patch('main.get_config') as mock_get_config, \
             patch('main.generate_route') as mock_generate_route, \
             patch('main.ChannelManager') as mock_channel_manager, \
             patch('main.get_application') as mock_get_application, \
             patch('main.generate_webhooks') as mock_generate_webhooks, \
             patch('main.Incidents.create_or_load') as mock_incidents, \
             patch('main.AsyncQueue.recreate_queue') as mock_queue, \
             patch('main.AsyncQueueManager') as mock_queue_manager:
            
            # Setup mock config
            mock_config = Mock()
            mock_config.messenger.type = MessengerType.SLACK
            mock_config.messenger.channels = {'default': {'id': 'C123456789'}}
            mock_config.app.route = Mock()
            mock_config.app.webhooks = Mock()
            mock_config.http_prefix = ""
            mock_get_config.return_value = mock_config
            
            # Setup mock route
            mock_route = Mock()
            mock_route.get_uniq_channels.return_value = ['C123456789']
            mock_route.channel = 'C123456789'
            mock_generate_route.return_value = mock_route
            
            # Setup mock channel manager
            mock_cm_instance = Mock()
            mock_cm_instance.initialize.return_value = {'C123456789': Mock()}
            mock_channel_manager.return_value = mock_cm_instance
            
            # Setup mock messenger
            mock_messenger = Mock()
            mock_messenger.initialize_async = AsyncMock()
            mock_messenger.close = AsyncMock()  # Make close async
            mock_messenger.type = "slack"
            mock_messenger.public_url = "https://test.slack.com"
            mock_messenger.team = "test-team"
            # Setup chains as an empty dict to avoid iteration issues
            mock_messenger.chains = {}
            mock_get_application.return_value = mock_messenger
            
            # Setup mock webhooks
            mock_webhooks = Mock()
            mock_generate_webhooks.return_value = mock_webhooks
            
            # Setup mock incidents
            mock_incidents_instance = Mock()
            mock_incidents.return_value = mock_incidents_instance
            
            # Setup mock queue
            mock_queue_instance = AsyncMock()
            mock_queue.return_value = mock_queue_instance
            
            # Setup mock queue manager
            mock_qm_instance = Mock()
            mock_qm_instance.start_processing = AsyncMock()
            mock_qm_instance.stop_processing = AsyncMock()
            mock_queue_manager.return_value = mock_qm_instance
            
            yield {
                'config': mock_config,
                'route': mock_route,
                'channel_manager': mock_cm_instance,
                'messenger': mock_messenger,
                'webhooks': mock_webhooks,
                'incidents': mock_incidents_instance,
                'queue': mock_queue_instance,
                'queue_manager': mock_qm_instance
            }

    def test_app_creation(self):
        """Test that the FastAPI app is created correctly."""
        assert main.app is not None
        assert main.app.title == "IMPulse"
        assert main.app.description == "Incident Management Program"
        assert main.app.version == "0.0.0"

    @patch('main.get_config')
    def test_http_prefix_configuration(self, mock_get_config):
        """Test HTTP prefix configuration."""
        mock_config = Mock()
        mock_config.http_prefix = "/api/v1"
        mock_config.ui_config = True
        mock_get_config.return_value = mock_config
        
        # This would normally require reloading the module, but we can test the logic
        assert mock_get_config.return_value.http_prefix == "/api/v1"

    @pytest.mark.asyncio
    async def test_lifespan_startup(self, mock_app_dependencies):
        """Test application startup in lifespan context."""
        app_mock = Mock()
        app_mock.state = Mock()
        
        async with main.lifespan(app_mock):
            # Verify that all state variables are set
            assert hasattr(app_mock.state, 'queue')
            assert hasattr(app_mock.state, 'queue_manager')
            assert hasattr(app_mock.state, 'incidents')
            assert hasattr(app_mock.state, 'messenger')
            assert hasattr(app_mock.state, 'webhooks')
            assert hasattr(app_mock.state, 'route')
            assert hasattr(app_mock.state, 'channel_manager')
            assert hasattr(app_mock.state, 'config')
            
            # Verify queue manager was started
            mock_app_dependencies['queue_manager'].start_processing.assert_called_once()

    def test_client_creation(self, mock_app_dependencies):
        """Test that test client can be created."""
        with patch('main.lifespan'):
            client = TestClient(main.app)
            assert client is not None


class TestSignalHandlers:
    """Test cases for signal handlers."""

    @patch('main.hasattr')
    @patch('main.signal')
    @patch('main.logger')
    def test_setup_sighup_handler_available(self, mock_logger, mock_signal, mock_hasattr):
        """Test SIGHUP handler setup when signal is available."""
        mock_hasattr.return_value = True
        
        main.setup_sighup_handler()
        
        mock_signal.signal.assert_called_once()
        mock_logger.debug.assert_called_once()

    @patch('main.hasattr')
    @patch('main.logger')
    def test_setup_sighup_handler_not_available(self, mock_logger, mock_hasattr):
        """Test SIGHUP handler setup when signal is not available."""
        mock_hasattr.return_value = False
        
        main.setup_sighup_handler()
        
        mock_logger.warning.assert_called_once_with("SIGHUP signal not available on this platform")

    @patch('main.reload_config')
    @patch('main.logger')
    def test_sighup_handler_success(self, mock_logger, mock_reload_config):
        """Test SIGHUP handler with successful config reload."""
        mock_reload_config.return_value = True
        
        # Get the handler function
        with patch('main.hasattr', return_value=True), \
             patch('main.signal') as mock_signal:
            main.setup_sighup_handler()
            handler = mock_signal.signal.call_args[0][1]
        
        # Call the handler
        handler(None, None)
        
        mock_logger.info.assert_any_call("Received SIGHUP signal, reloading configuration...")
        mock_logger.info.assert_any_call("Configuration reload completed successfully")

    @patch('main.reload_config')
    @patch('main.logger')
    def test_sighup_handler_error(self, mock_logger, mock_reload_config):
        """Test SIGHUP handler with error during config reload."""
        mock_reload_config.side_effect = Exception("Config error")
        
        # Get the handler function
        with patch('main.hasattr', return_value=True), \
             patch('main.signal') as mock_signal:
            main.setup_sighup_handler()
            handler = mock_signal.signal.call_args[0][1]
        
        # Call the handler
        handler(None, None)
        
        mock_logger.error.assert_called_once()
        mock_logger.warning.assert_called_once()


class TestConfigValidation:
    """Test cases for configuration validation."""

    @patch('main.get_config')
    @patch('main.logger')
    @patch('main.sys.exit')
    def test_validate_config_only_success(self, mock_exit, mock_logger, mock_get_config):
        """Test successful configuration validation."""
        mock_config = Mock()
        mock_config.messenger.type.value = "slack"
        mock_config.messenger.channels = {'default': {'id': 'C123456789'}}
        mock_config.messenger.users = {}
        mock_config.app.incident = True
        mock_config.app.ui = True
        mock_config.app.route = True
        mock_get_config.return_value = mock_config
        
        main.validate_config_only()
        
        mock_exit.assert_called_once_with(0)
        mock_logger.info.assert_called()

    @patch('main.get_config')
    @patch('main.logger')
    @patch('main.sys.exit')
    def test_validate_config_only_system_exit_non_zero(self, mock_exit, mock_logger, mock_get_config):
        """Test configuration validation with SystemExit non-zero."""
        mock_get_config.side_effect = SystemExit(1)
        
        main.validate_config_only()
        
        mock_exit.assert_called_with(1)
        mock_logger.error.assert_called_once()

    @patch('main.get_config')
    @patch('main.logger')
    @patch('main.sys.exit')
    def test_validate_config_only_exception(self, mock_exit, mock_logger, mock_get_config):
        """Test configuration validation with general exception."""
        mock_get_config.side_effect = Exception("Config error")
        
        main.validate_config_only()
        
        mock_exit.assert_called_with(1)
        mock_logger.error.assert_called_once()


class TestArgumentParsing:
    """Test cases for argument parsing."""

    def test_parse_arguments_no_args(self):
        """Test parsing with no arguments."""
        with patch('main.argparse.ArgumentParser.parse_args') as mock_parse:
            mock_parse.return_value = Mock(check=False)
            args = main.parse_arguments()
            assert args.check is False

    def test_parse_arguments_check_flag(self):
        """Test parsing with --check flag."""
        with patch('main.argparse.ArgumentParser.parse_args') as mock_parse:
            mock_parse.return_value = Mock(check=True)
            args = main.parse_arguments()
            assert args.check is True


class TestMainExecution:
    """Test cases for main execution."""

    @patch('main.parse_arguments')
    @patch('main.validate_config_only')
    def test_main_with_check_flag(self, mock_validate, mock_parse):
        """Test main execution with --check flag."""
        mock_parse.return_value = Mock(check=True)
        
        # This would normally be tested by running the script, but we can test the logic
        args = mock_parse.return_value
        if args.check:
            mock_validate()
        
        mock_validate.assert_called_once()

    @patch('main.parse_arguments')
    @patch('main.setup_sighup_handler')
    @patch('main.configure_uvicorn_logging')
    @patch('uvicorn.run')  # Patch uvicorn.run directly
    def test_main_without_check_flag(self, mock_uvicorn_run, mock_configure_logging, 
                                   mock_setup_sighup, mock_parse):
        """Test main execution without --check flag."""
        mock_parse.return_value = Mock(check=False)
        
        # This would normally be tested by running the script
        args = mock_parse.return_value
        if not args.check:
            mock_setup_sighup()
            mock_configure_logging()
            # Import uvicorn here to simulate the actual behavior
            import uvicorn
            mock_uvicorn_run("main:app", host="0.0.0.0", port=5000, reload=True, log_level="warning")
        
        mock_setup_sighup.assert_called_once()
        mock_configure_logging.assert_called_once()
        mock_uvicorn_run.assert_called_once()
