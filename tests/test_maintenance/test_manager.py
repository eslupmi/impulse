"""
Unit tests for MaintenanceManager.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from app.incident.freeze import FreezeSource, MAINTENANCE_PARENT_SENTINEL
from app.maintenance.manager import MaintenanceManager
from app.maintenance.models import MaintenanceWindow
from app.incident.incident import Incident, IncidentConfig
from app.queue.constants import QueueItemType
from tests.utils import create_alert_payload


TEST_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)


def _incident(**label_overrides):
    alertname = label_overrides.pop("alertname", "TestAlert")
    payload = create_alert_payload(status="firing", alertname=alertname, **label_overrides)
    return Incident(
        payload=payload,
        status="firing",
        channel_id="C1",
        config=IncidentConfig("slack", "https://test.slack.com", "team"),
        status_update_datetime=datetime.now(timezone.utc),
        assigned_user_id="",
        assigned_user="",
        assigned_fullname="",
        messenger_type="slack",
    )


def _window(start_offset_hours=0, duration_hours=2, matchers=None):
    return MaintenanceWindow(
        starts_at=TEST_NOW - timedelta(hours=start_offset_hours),
        ends_at=TEST_NOW + timedelta(hours=duration_hours),
        matchers=matchers or ['alertname = "TestAlert"'],
    )


@pytest.fixture
def maintenance_setup():
    store = Mock()
    store.list = Mock(return_value=[])
    incidents = Mock()
    incidents.uniq_ids = {}
    application = Mock()
    application.apply_time_freeze = AsyncMock()
    application.update_incident_message = AsyncMock()
    queue = Mock()
    queue.delete_by_id_and_type = AsyncMock()
    queue.delete_by_id = AsyncMock()
    queue.put = AsyncMock()
    queue.put_first = AsyncMock()
    queue.recreate = AsyncMock()
    manager = MaintenanceManager(store, incidents, application, queue, now=lambda: TEST_NOW)
    return manager, store, application, queue


class TestMaintenanceManager:
    @pytest.mark.asyncio
    async def test_process_incident_applies_freeze_when_window_matches(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        window = _window()
        store.list.return_value = [window]
        incident = _incident()

        await manager.process_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        application.apply_time_freeze.assert_awaited_once_with(
            incident, window.ends_at, user=None, queue_=manager.queue, source=FreezeSource.MAINTENANCE
        )

    @pytest.mark.asyncio
    async def test_process_incident_defers_when_inhibition_holds(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        store.list.return_value = [_window()]
        incident = _incident()
        incident.parents.append("source-uniq-id")

        await manager.process_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        assert incident.frozen_by_maintenance is True
        application.apply_time_freeze.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconcile_clears_sentinel_when_no_active_window(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        store.list.return_value = []
        incident = _incident()
        incident.parents = [MAINTENANCE_PARENT_SENTINEL]

        await manager.reconcile_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL not in incident.parents
        assert incident.frozen_by_maintenance is False
        application.apply_time_freeze.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconcile_removes_maintenance_source_when_no_other_window(self, maintenance_setup):
        manager, store, _, _ = maintenance_setup
        store.list.return_value = []
        incident = _incident()
        incident.parents = [MAINTENANCE_PARENT_SENTINEL]
        incident.frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        incident.frozen_until_source = FreezeSource.MAINTENANCE.value
        incident.ts = "123.456"

        await manager.reconcile_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL not in incident.parents
        assert incident.frozen_until is None

    @pytest.mark.asyncio
    async def test_reconcile_preserves_manual_freeze_when_maintenance_deleted(self, maintenance_setup):
        manager, store, _, _ = maintenance_setup
        store.list.return_value = []
        incident = _incident()
        manual_until = datetime.now(timezone.utc) + timedelta(hours=1)
        incident.parents = [MAINTENANCE_PARENT_SENTINEL]
        incident.frozen_until = manual_until
        incident.frozen_until_source = FreezeSource.TIME.value
        incident.ts = "123.456"

        await manager.reconcile_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL not in incident.parents
        assert incident.frozen_until == manual_until

    @pytest.mark.asyncio
    async def test_reconcile_schedules_maintenance_when_window_matches(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        window = _window()
        store.list.return_value = [window]
        incident = _incident()
        incident.parents = [MAINTENANCE_PARENT_SENTINEL]

        await manager.reconcile_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        assert incident.frozen_until == window.ends_at
        assert incident.frozen_until_source == FreezeSource.MAINTENANCE.value
        application.apply_time_freeze.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconcile_after_window_removed_only_affects_matching_incidents(self, maintenance_setup):
        manager, store, _, _ = maintenance_setup
        removed = _window(matchers=['alertname = "OtherAlert"'])
        matching = _incident()
        matching.parents = [MAINTENANCE_PARENT_SENTINEL]
        other = _incident(alertname="OtherAlert")
        other.parents = [MAINTENANCE_PARENT_SENTINEL]
        manager.incidents.uniq_ids = {"a": matching, "b": other}
        store.list.return_value = []

        await manager.reconcile_after_window_removed(removed)

        assert MAINTENANCE_PARENT_SENTINEL not in other.parents
        assert MAINTENANCE_PARENT_SENTINEL in matching.parents

    @pytest.mark.asyncio
    async def test_reconcile_reschedules_when_overlap_window_exists(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        window = _window(duration_hours=1)
        store.list.return_value = [window]
        incident = _incident()
        incident.ts = "1.2"

        await manager.reconcile_incident(incident)

        assert incident.frozen_until == window.ends_at
        assert incident.frozen_until_source == FreezeSource.MAINTENANCE.value
        assert incident.frozen_by_maintenance is True
        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        application.apply_time_freeze.assert_not_called()
        manager.queue.put.assert_awaited_once_with(
            window.ends_at,
            QueueItemType.UNFREEZE,
            incident.uniq_id,
            data=FreezeSource.MAINTENANCE.value,
        )
        application.update_incident_message.assert_awaited_once_with(incident)

    @pytest.mark.asyncio
    async def test_reconcile_strips_sentinel_when_window_ended(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        store.list.return_value = []
        incident = _incident()
        incident.parents = [MAINTENANCE_PARENT_SENTINEL]
        incident.ts = "1.2"

        await manager.reconcile_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL not in incident.parents
        application.update_incident_message.assert_awaited_once_with(incident)
