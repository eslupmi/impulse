"""
Unit tests for app.queue.handlers module.
"""
from unittest.mock import Mock, AsyncMock, patch

import pytest

from app.queue.handlers.alert_handler import AlertHandler
from app.queue.handlers.base_handler import BaseHandler
from app.queue.handlers.status_update_handler import StatusUpdateHandler
from app.queue.handlers.step_handler import StepHandler
from tests.utils import (
    create_mock_config, create_alert_payload, create_test_datetime,
    create_mock_queue, create_mock_application, create_mock_incidents_collection,
    create_mock_route, create_mock_webhooks_collection, create_mock_incident_for_handlers
)


class TestBaseHandler:
    """Test cases for BaseHandler class."""

    def test_base_handler_initialization(self):
        """Test BaseHandler initialization."""
        # BaseHandler is abstract, so we can't instantiate it directly
        with pytest.raises(TypeError):
            BaseHandler()

    def test_base_handler_abstract_methods(self):
        """Test that BaseHandler has abstract handle method."""
        from abc import ABC

        assert issubclass(BaseHandler, ABC)
        assert hasattr(BaseHandler, 'handle')


class TestAlertHandler:
    """Test cases for AlertHandler class."""

    @pytest.fixture
    def mock_queue(self):
        """Create mock queue."""
        return create_mock_queue()

    @pytest.fixture
    def mock_application(self):
        """Create mock application."""
        return create_mock_application()

    @pytest.fixture
    def mock_incidents(self):
        """Create mock incidents collection."""
        return create_mock_incidents_collection()

    @pytest.fixture
    def mock_route(self):
        """Create mock route."""
        return create_mock_route()

    @pytest.fixture
    def mock_inhibition_manager(self):
        """Create mock inhibition manager."""
        manager = Mock()
        manager.process_incident = AsyncMock()
        manager.handle_resolved = AsyncMock()
        manager.handle_closed = AsyncMock()
        manager.would_be_inhibited = Mock(return_value=False)
        return manager

    @pytest.fixture
    def mock_maintenance_manager(self):
        """Create mock maintenance manager."""
        manager = Mock()
        manager.process_incident = AsyncMock()
        manager.would_match_active_window = Mock(return_value=False)
        manager.reconcile_incident = AsyncMock()
        manager.reconcile_all = AsyncMock()
        return manager

    @pytest.fixture
    def alert_handler(self, mock_queue, mock_application, mock_incidents, mock_route, mock_inhibition_manager, mock_maintenance_manager):
        """Create AlertHandler instance for testing."""
        return AlertHandler(mock_queue, mock_application, mock_incidents, mock_route, mock_inhibition_manager, mock_maintenance_manager)

    def test_alert_handler_initialization(self, mock_queue, mock_application, mock_incidents, mock_route, mock_inhibition_manager, mock_maintenance_manager):
        """Test AlertHandler initialization."""
        handler = AlertHandler(mock_queue, mock_application, mock_incidents, mock_route, mock_inhibition_manager, mock_maintenance_manager)

        assert handler.queue == mock_queue
        assert handler.app == mock_application
        assert handler.incidents == mock_incidents
        assert handler.route == mock_route

    @pytest.mark.asyncio
    async def test_handle_existing_incident(self, alert_handler, mock_incidents, mock_application, mock_queue):
        """Test handling existing incident update."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )

        # Mock existing incident
        mock_incident = create_mock_incident_for_handlers(
            uuid='test-uuid-123',
            status='firing',
            update_state_return=(True, True)  # Status and state updated
        )
        mock_incidents.get.return_value = mock_incident

        with patch('app.queue.handlers.alert_handler.get_config') as mock_get_config:
            # Use utility function for mock config
            mock_config = create_mock_config()
            mock_config.incident.notifications.new_firing = True
            mock_config.incident.notifications.partial_resolved = True
            mock_get_config.return_value = mock_config

            await alert_handler.handle(alert_payload)

            # Should update existing incident
            mock_incident.update_state.assert_called_once_with(alert_payload)
            mock_application.update.assert_called_once()
            mock_queue.recreate.assert_called_once()
            mock_queue.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_incident_no_changes(self, alert_handler, mock_incidents, mock_application, mock_queue):
        """Test handling incident with no changes."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )

        # Mock existing incident with no changes
        mock_incident = Mock()
        mock_incident.uuid = 'test-uuid-123'
        mock_incident.status = 'firing'
        mock_incident.chain_enabled = True
        mock_incident.chain = []
        mock_incident.status_enabled = True
        mock_incident.update_state.return_value = (False, False)  # No changes
        mock_incident.is_new_firing_alerts_added.return_value = False
        mock_incident.is_some_firing_alerts_removed.return_value = False
        mock_incident.get_chain.return_value = []
        mock_incident.status_update_datetime = create_test_datetime()
        mock_incidents.get.return_value = mock_incident

        with patch('app.queue.handlers.alert_handler.get_config') as mock_get_config:
            # Use utility function for mock config
            mock_config = create_mock_config()
            mock_config.incident.notifications.new_firing = True
            mock_config.incident.notifications.partial_resolved = True
            mock_get_config.return_value = mock_config

            await alert_handler.handle(alert_payload)

            # Should not call update if no changes
            mock_incident.update_state.assert_called_once_with(alert_payload)
            mock_application.update.assert_not_called()
            mock_queue.recreate.assert_called_once()
            mock_queue.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_create_aborts_when_thread_creation_fails(
        self, alert_handler, mock_incidents, mock_application, mock_queue, mock_inhibition_manager
    ):
        """If create_incident_message returns None, no incident is stored or scheduled."""
        alert_payload = create_alert_payload(status="firing")
        mock_incidents.get.return_value = None

        mock_application.form_body_header_status_icons = Mock(return_value=("b", "h", "s"))
        mock_application.create_incident_message = AsyncMock(return_value=None)

        with patch('app.queue.handlers.alert_handler.get_config') as mock_get_config:
            mock_get_config.return_value = create_mock_config()

            await alert_handler.handle(alert_payload)

        mock_application.create_incident_message.assert_awaited_once()
        mock_incidents.add.assert_not_called()
        mock_inhibition_manager.process_incident.assert_not_called()
        mock_queue.put.assert_not_called()
        mock_queue.recreate.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_create_aborts_when_thread_id_is_none_none(
        self, alert_handler, mock_incidents, mock_application, mock_queue, mock_inhibition_manager
    ):
        """Telegram-style 'None/None' id must be treated as failure."""
        alert_payload = create_alert_payload(status="firing")
        mock_incidents.get.return_value = None

        mock_application.form_body_header_status_icons = Mock(return_value=("b", "h", "s"))
        mock_application.create_incident_message = AsyncMock(return_value='None/None')

        with patch('app.queue.handlers.alert_handler.get_config') as mock_get_config:
            mock_get_config.return_value = create_mock_config()

            await alert_handler.handle(alert_payload)

        mock_incidents.add.assert_not_called()
        mock_inhibition_manager.process_incident.assert_not_called()
        mock_queue.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_exception(self, alert_handler, mock_incidents):
        """Test handling exception during processing."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )

        # Mock incidents.get to raise exception
        mock_incidents.get.side_effect = Exception("Database error")

        # Should raise exception (AlertHandler doesn't catch exceptions)
        with pytest.raises(Exception, match="Database error"):
            await alert_handler.handle(alert_payload)


class TestStatusUpdateHandler:
    """Test cases for StatusUpdateHandler class."""

    @pytest.fixture
    def mock_queue(self):
        """Create mock queue."""
        return create_mock_queue()

    @pytest.fixture
    def mock_application(self):
        """Create mock application."""
        return create_mock_application()

    @pytest.fixture
    def mock_incidents(self):
        """Create mock incidents collection."""
        return create_mock_incidents_collection(include_get_method=False)

    @pytest.fixture
    def mock_inhibition_manager(self):
        """Create mock inhibition manager."""
        manager = Mock()
        manager.process_incident = AsyncMock()
        manager.handle_resolved = AsyncMock()
        manager.handle_closed = AsyncMock()
        return manager

    @pytest.fixture
    def status_update_handler(self, mock_queue, mock_application, mock_incidents, mock_inhibition_manager):
        """Create StatusUpdateHandler instance for testing."""
        return StatusUpdateHandler(mock_queue, mock_application, mock_incidents, mock_inhibition_manager)

    def test_status_update_handler_initialization(self, mock_queue, mock_application, mock_incidents, mock_inhibition_manager):
        """Test StatusUpdateHandler initialization."""
        handler = StatusUpdateHandler(mock_queue, mock_application, mock_incidents, mock_inhibition_manager)

        assert handler.queue == mock_queue
        assert handler.app == mock_application
        assert handler.incidents == mock_incidents

    @pytest.mark.asyncio
    async def test_handle_existing_incident(self, status_update_handler, mock_incidents, mock_application, mock_queue):
        """Test handling status update for existing incident."""
        incident_uniq_id = 'incident123'

        # Mock existing incident
        mock_incident = Mock()
        mock_incident.status = 'firing'
        mock_incident.chain_enabled = True
        mock_incident.status_enabled = True
        mock_incident.payload = {'alertname': 'TestAlert'}
        mock_incident.status_update_datetime = create_test_datetime()
        mock_incident.next_status = {
            'firing': 'unknown',
            'unknown': 'closed',
            'resolved': 'closed',
            'closed': 'deleted'
        }
        
        # Mock update_status to change status to 'unknown'
        def update_status_side_effect(new_status):
            mock_incident.status = new_status
            return True
        mock_incident.update_status = Mock(side_effect=update_status_side_effect)
        
        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.remove_file = Mock()

        await status_update_handler.handle(incident_uniq_id)

        # Should call update_status and update
        mock_incident.update_status.assert_called_once_with('unknown')
        mock_application.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_incident_status_closed(self, status_update_handler, mock_incidents, mock_application,
                                                 mock_queue):
        """Test handling incident with status changed to closed."""
        incident_uniq_id = 'incident123'

        # Mock incident with status 'closed'
        mock_incident = Mock()
        mock_incident.status = 'closed'
        mock_incident.chain_enabled = True
        mock_incident.status_enabled = True
        mock_incident.payload = {'alertname': 'TestAlert'}
        mock_incident.status_update_datetime = create_test_datetime()
        mock_incident.next_status = {
            'firing': 'unknown',
            'unknown': 'closed',
            'resolved': 'closed',
            'closed': 'deleted'
        }
        
        # Mock update_status to change status to 'deleted'
        def update_status_side_effect(new_status):
            mock_incident.status = new_status
            return True
        mock_incident.update_status = Mock(side_effect=update_status_side_effect)
        
        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.remove_file = Mock()
        mock_incidents.del_by_uniq_id = Mock()

        await status_update_handler.handle(incident_uniq_id)

        # Should update status to 'deleted'
        # app.update should NOT be called when status is 'deleted'
        mock_incident.update_status.assert_called_once_with('deleted')
        mock_application.update.assert_not_called()
        mock_queue.put_first.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_incident_status_unknown(self, status_update_handler, mock_incidents, mock_application,
                                                  mock_queue):
        """Test handling incident with status changed from unknown to closed."""
        incident_uniq_id = 'incident123'

        # Mock incident with status 'unknown'
        mock_incident = Mock()
        mock_incident.status = 'unknown'
        mock_incident.chain_enabled = True
        mock_incident.status_enabled = True
        mock_incident.payload = {'alertname': 'TestAlert'}
        mock_incident.status_update_datetime = create_test_datetime()
        mock_incident.next_status = {
            'firing': 'unknown',
            'unknown': 'closed',
            'resolved': 'closed',
            'closed': 'deleted'
        }
        
        # Mock update_status to change status to 'closed'
        def update_status_side_effect(new_status):
            mock_incident.status = new_status
            return True
        mock_incident.update_status = Mock(side_effect=update_status_side_effect)
        
        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.remove_file = Mock()

        await status_update_handler.handle(incident_uniq_id)

        # Should update status to 'closed' and update queue
        # app.update() should be called to update messenger with closed status
        mock_incident.update_status.assert_called_once_with('closed')
        mock_application.update.assert_called_once()  # Called to update messenger with closed status
        mock_queue.update.assert_called_once()
        mock_queue.delete_by_id.assert_called_once_with(incident_uniq_id, delete_steps=True, delete_status=False)
        mock_queue.put_first.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_incident_no_status_change(self, status_update_handler, mock_incidents, mock_application,
                                                    mock_queue):
        """Test handling incident with no status change."""
        incident_uniq_id = 'incident123'

        # Mock incident with no status change
        mock_incident = Mock()
        mock_incident.status = 'firing'
        mock_incident.chain_enabled = True
        mock_incident.status_enabled = True
        mock_incident.payload = {'alertname': 'TestAlert'}
        mock_incident.status_update_datetime = create_test_datetime()
        mock_incident.next_status = {
            'firing': 'unknown',
            'unknown': 'closed',
            'resolved': 'closed',
            'closed': 'deleted'
        }
        
        # Mock update_status to return False (no status change)
        def update_status_side_effect(new_status):
            # Status doesn't change if update_status returns False
            return False
        mock_incident.update_status = Mock(side_effect=update_status_side_effect)
        
        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.remove_file = Mock()

        await status_update_handler.handle(incident_uniq_id)

        # Should still call update_status and update
        mock_incident.update_status.assert_called_once_with('unknown')
        # Status is still 'firing', so app.update should be called
        mock_application.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_nonexistent_incident(self, status_update_handler, mock_incidents):
        """Test handling status update for non-existent incident."""
        incident_uniq_id = 'nonexistent123'
        mock_incidents.uniq_ids = {}

        # The handler returns early for None incident, so it should not raise an error
        await status_update_handler.handle(incident_uniq_id)


class TestStepHandler:
    """Test cases for StepHandler class."""

    @pytest.fixture
    def mock_queue(self):
        """Create mock queue."""
        return create_mock_queue()

    @pytest.fixture
    def mock_application(self):
        """Create mock application."""
        return create_mock_application()

    @pytest.fixture
    def mock_incidents(self):
        """Create mock incidents collection."""
        return create_mock_incidents_collection(include_get_method=False)

    @pytest.fixture
    def mock_webhooks(self):
        """Create mock webhooks collection."""
        return create_mock_webhooks_collection()

    @pytest.fixture
    def step_handler(self, mock_queue, mock_application, mock_incidents, mock_webhooks):
        """Create StepHandler instance for testing."""
        return StepHandler(mock_queue, mock_application, mock_incidents, mock_webhooks)

    def test_step_handler_initialization(self, mock_queue, mock_application, mock_incidents, mock_webhooks):
        """Test StepHandler initialization."""
        handler = StepHandler(mock_queue, mock_application, mock_incidents, mock_webhooks)

        assert handler.queue == mock_queue
        assert handler.app == mock_application
        assert handler.incidents == mock_incidents
        assert handler.webhooks == mock_webhooks


    @pytest.mark.asyncio
    async def test_handle_non_webhook_step(self, step_handler, mock_incidents, mock_application):
        """Test handling non-webhook step."""
        incident_uniq_id = 'incident123'
        identifier = 0

        # Mock incident with non-webhook step
        mock_incident = Mock()
        mock_incident.uuid = 'uuid123'
        mock_incident.channel_id = 'C123456789'
        mock_incident.ts = '1234567890.123456'
        mock_incident.payload = {'alertname': 'TestAlert'}
        mock_incident.chain = [
            {'type': 'user', 'identifier': 'testuser', 'done': False}
        ]
        mock_incident.chain_update = Mock()
        mock_incident.is_frozen = False
        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await step_handler.handle(incident_uniq_id, identifier)

        # Should call app.notify
        mock_application.notify.assert_called_once_with(mock_incident, 'user', 'testuser')
        mock_incident.chain_update.assert_called_once_with(identifier, done=True, result=200)

    @pytest.mark.asyncio
    async def test_handle_nonexistent_incident(self, step_handler, mock_incidents):
        """Test handling step for non-existent incident."""
        incident_uniq_id = 'nonexistent123'
        identifier = 0

        # Mock non-existent incident
        mock_incidents.uniq_ids = {}

        # Should raise KeyError (StepHandler doesn't catch exceptions)
        with pytest.raises(KeyError):
            await step_handler.handle(incident_uniq_id, identifier)
