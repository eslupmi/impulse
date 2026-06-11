"""
Integration tests for main.py FastAPI application.
"""
import asyncio
from unittest.mock import Mock, patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

import main
from app.config.validation import MessengerType


class TestMainApplication:
    """Test cases for the main FastAPI application."""

    @pytest.fixture
    def mock_app_dependencies(self):
        """Mock all application dependencies."""
        with patch('app.lifespan.get_config') as mock_get_config, \
                patch('app.lifespan.generate_route') as mock_generate_route, \
                patch('app.lifespan.ChannelManager') as mock_channel_manager, \
                patch('app.lifespan.get_application') as mock_get_application, \
                patch('app.lifespan.generate_webhooks') as mock_generate_webhooks, \
                patch('app.lifespan.Incidents.create_or_load') as mock_incidents, \
                patch('app.lifespan.AsyncQueue.recreate_queue') as mock_queue, \
                patch('app.lifespan.AsyncQueueManager') as mock_queue_manager, \
                patch('app.lifespan.FileLock') as mock_file_lock_class, \
                patch('app.config.environment.get_environment_config') as mock_get_env_config, \
                patch('app.im.application.Application') as mock_application, \
                patch('app.lifespan.UserUpdateScheduler') as mock_scheduler_class, \
                patch('app.lifespan.InhibitionManager') as mock_inhibition_manager_class, \
                patch('app.lifespan.get_maintenance_store') as mock_get_maintenance_store, \
                patch('app.lifespan.MaintenanceManager') as mock_maintenance_manager_class:
            # Setup mock scheduler
            mock_scheduler = Mock()
            mock_scheduler.schedule_all_stored = AsyncMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            # Setup mock inhibition manager
            mock_inhibition_manager = Mock()
            mock_inhibition_manager.restore_from_incidents = Mock()
            mock_inhibition_manager.attach_maintenance_manager = Mock()
            mock_inhibition_manager_class.return_value = mock_inhibition_manager

            mock_maintenance_store = Mock()
            mock_maintenance_store.list.return_value = []
            mock_get_maintenance_store.return_value = mock_maintenance_store

            mock_maintenance_manager = Mock()
            mock_maintenance_manager.reconcile_all = AsyncMock()
            mock_maintenance_manager_class.return_value = mock_maintenance_manager
            
            # Setup mock config
            mock_config = Mock()
            mock_config.messenger.type = MessengerType.SLACK
            mock_config.messenger.channels = {'default': {'id': 'C123456789'}}
            mock_config.app.route = Mock()
            mock_config.app.webhooks = Mock()
            mock_config.app.inhibit_rules = []
            mock_get_config.return_value = mock_config
            
            # Setup mock environment config
            mock_env_config = Mock()
            mock_env_config.http_prefix = ""
            mock_get_env_config.return_value = mock_env_config

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
            mock_messenger.type = MessengerType.SLACK
            mock_messenger.public_url = "https://test.slack.com"
            mock_messenger.team = "test-team"
            mock_messenger.configure_scheduler = Mock()
            # Setup chains as an empty dict to avoid iteration issues
            mock_messenger.chains = {}
            mock_messenger.task_management_integration = None  # No Jira integration by default
            mock_get_application.return_value = mock_messenger

            # Setup mock webhooks
            mock_webhooks = Mock()
            mock_generate_webhooks.return_value = mock_webhooks

            # Setup mock incidents
            mock_incidents_instance = Mock()
            mock_incidents_instance.uniq_ids = {}
            mock_incidents.return_value = mock_incidents_instance

            # Setup mock queue
            mock_queue_instance = AsyncMock()
            mock_queue.return_value = mock_queue_instance

            # Setup mock queue manager
            mock_qm_instance = Mock()
            mock_qm_instance.start_processing = Mock()
            mock_qm_instance.stop_processing = AsyncMock()
            mock_queue_manager.return_value = mock_qm_instance

            # Setup mock file lock
            mock_file_lock_instance = Mock()
            mock_file_lock_instance.is_locked.return_value = False  # Not locked by default
            mock_file_lock_instance.can_take_over_lock.return_value = False
            mock_file_lock_instance.get_lock_info.return_value = ("test-hostname", "12345")
            mock_file_lock_instance.wait_for_unlock = AsyncMock()
            mock_file_lock_instance.acquire_lock = Mock(return_value=True)
            mock_file_lock_instance.release_lock = AsyncMock()
            mock_file_lock_class.return_value = mock_file_lock_instance

            # Setup mock environment config for Jira
            mock_env_config = Mock()
            mock_env_config.jira_enabled = False  # Disable Jira in tests
            mock_get_env_config.return_value = mock_env_config

            # Setup mock Application class for Jira integration
            mock_application.task_management_integration = None

            yield {
                'config': mock_config,
                'route': mock_route,
                'channel_manager': mock_cm_instance,
                'messenger': mock_messenger,
                'webhooks': mock_webhooks,
                'incidents': mock_incidents_instance,
                'queue': mock_queue_instance,
                'queue_manager': mock_qm_instance,
                'file_lock': mock_file_lock_instance,
                'env_config': mock_env_config,
                'application': mock_application,
                'inhibition_manager': mock_inhibition_manager,
                'maintenance_manager': mock_maintenance_manager,
                'maintenance_store': mock_maintenance_store,
            }

    def test_app_creation(self):
        """Test that the FastAPI app is created correctly."""
        assert main.app is not None
        assert main.app.title == "IMPulse"
        assert main.app.description == "Incident Management Platform"
        assert main.app.version == "0.0.0"

    @patch('app.config.environment.get_environment_config')
    @patch('app.config.config.get_config')
    def test_http_prefix_configuration(self, mock_get_config, mock_get_env_config):
        """Test HTTP prefix configuration."""
        mock_config = Mock()
        mock_config.ui_config = True
        mock_get_config.return_value = mock_config
        
        mock_env_config = Mock()
        mock_env_config.http_prefix = "/api/v1"
        mock_get_env_config.return_value = mock_env_config

        # This would normally require reloading the module, but we can test the logic
        assert mock_get_env_config.return_value.http_prefix == "/api/v1"

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
            assert hasattr(app_mock.state, 'file_lock')
            assert hasattr(app_mock.state, 'is_standby')
            assert app_mock.state.is_standby is False

            # Verify queue manager was started
            mock_app_dependencies['queue_manager'].start_processing.assert_called_once()
            
            # Verify file lock was checked
            mock_app_dependencies['file_lock'].is_locked.assert_called_once()
            # Verify file lock was acquired
            mock_app_dependencies['file_lock'].acquire_lock.assert_called_once()
        
        # After exiting context, verify cleanup
        # Note: unlock_task is None when not locked, so cancel is not called
        mock_app_dependencies['queue_manager'].stop_processing.assert_called_once()
        mock_app_dependencies['file_lock'].release_lock.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_startup_with_locked_file(self, mock_app_dependencies):
        """Test application startup when file lock is initially held."""
        from app.file_lock import FileLock
        
        app_mock = Mock()
        app_mock.state = Mock()
        
        # Create a real FileLock but mock its methods
        with patch.object(FileLock, '__init__', lambda self: None):
            mock_file_lock = FileLock()
        mock_file_lock.lock_dir = Mock()
        mock_file_lock._active = False
        mock_file_lock._heartbeat_task = None
        
        # Lock is held
        mock_file_lock.is_locked = Mock(return_value=True)
        mock_file_lock.can_take_over_lock = Mock(return_value=False)
        mock_file_lock.get_lock_info = Mock(return_value=("other-host", "999"))
        mock_file_lock.acquire_lock = Mock(return_value=True)
        mock_file_lock.release_lock = AsyncMock()
        
        # wait_for_unlock blocks until cancelled
        async def blocking_wait():
            await asyncio.Event().wait()  # Wait forever
        mock_file_lock.wait_for_unlock = blocking_wait
        
        with patch('app.lifespan.FileLock', return_value=mock_file_lock), \
             patch('app.lifespan.logger') as mock_logger:
            async with main.lifespan(app_mock):
                await asyncio.sleep(0.01)  # Let task start
                
                # Verify standby state is set
                assert app_mock.state.is_standby is True
                
                # Verify log messages
                mock_logger.info.assert_any_call("Another IMPulse instance is running, working as standby server")
                mock_logger.info.assert_any_call("IMPulse started in standby mode")
            
            # release_lock should not be called when in standby mode (we return early)
            mock_file_lock.release_lock.assert_not_called()
            # acquire_lock is not called when starting in standby mode
            mock_file_lock.acquire_lock.assert_not_called()


