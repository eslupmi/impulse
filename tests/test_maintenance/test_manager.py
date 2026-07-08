"""
Unit tests for MaintenanceManager.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock, patch

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


def _fixed_window(starts_at, ends_at, matchers=None):
    return MaintenanceWindow(
        starts_at=starts_at,
        ends_at=ends_at,
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
    queue.delete_by_id_type_and_data = AsyncMock()
    queue.delete_by_type = AsyncMock()
    queue.delete_by_id = AsyncMock()
    queue.put = AsyncMock()
    queue.put_first = AsyncMock()
    queue.recreate = AsyncMock()
    manager = MaintenanceManager(store, incidents, application, queue, now=lambda: TEST_NOW)
    return manager, store, application, queue


class TestMaintenanceManager:
    @pytest.mark.asyncio
    async def test_schedule_window_starts_queues_future_windows(self, maintenance_setup):
        manager, store, _, queue = maintenance_setup
        active = _fixed_window(TEST_NOW - timedelta(hours=1), TEST_NOW + timedelta(hours=1))
        future = _fixed_window(TEST_NOW + timedelta(minutes=5), TEST_NOW + timedelta(hours=2))
        store.list.return_value = [future, active]

        await manager.schedule_window_starts()

        queue.delete_by_type.assert_any_await(QueueItemType.MAINTENANCE_START)
        queue.delete_by_type.assert_any_await(QueueItemType.MAINTENANCE_END)
        queue.put.assert_any_await(
            future.starts_at,
            QueueItemType.MAINTENANCE_START,
            identifier=future.id,
        )
        queue.put.assert_any_await(
            active.ends_at,
            QueueItemType.MAINTENANCE_END,
            identifier=active.id,
        )

    @pytest.mark.asyncio
    async def test_handle_window_start_reconciles_when_window_is_active(self, maintenance_setup):
        manager, store, _, _ = maintenance_setup
        window = _window()
        store.list.return_value = [window]
        incident = _incident()
        manager.incidents.uniq_ids = {incident.uniq_id: incident}

        await manager.handle_window_start(window.id)

        assert incident.frozen_until == window.ends_at
        assert incident.frozen_until_source == FreezeSource.MAINTENANCE.value

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
        application.update_incident_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_incident_updates_posted_message_after_freeze(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        window = _window()
        store.list.return_value = [window]
        incident = _incident()
        incident.ts = "1.2"

        await manager.process_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        application.apply_time_freeze.assert_awaited_once_with(
            incident, window.ends_at, user=None, queue_=manager.queue, source=FreezeSource.MAINTENANCE
        )
        application.update_incident_message.assert_awaited_once_with(incident)

    @pytest.mark.asyncio
    async def test_process_incident_freezes_until_connected_matching_window_end(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        first = _fixed_window(TEST_NOW - timedelta(hours=1), TEST_NOW + timedelta(hours=1))
        second = _fixed_window(first.ends_at, first.ends_at + timedelta(hours=2))
        store.list.return_value = [first, second]
        incident = _incident()

        await manager.process_incident(incident)

        application.apply_time_freeze.assert_awaited_once_with(
            incident, second.ends_at, user=None, queue_=manager.queue, source=FreezeSource.MAINTENANCE
        )

    @pytest.mark.asyncio
    async def test_process_incident_defers_when_inhibition_holds(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        window = _window()
        store.list.return_value = [window]
        incident = _incident()
        incident.parents.append("source-uniq-id")

        await manager.process_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        assert incident.frozen_by_maintenance is True
        assert incident.frozen_until == window.ends_at
        assert incident.frozen_until_source == FreezeSource.MAINTENANCE.value
        manager.queue.put.assert_awaited_once_with(
            window.ends_at,
            QueueItemType.UNFREEZE,
            incident.uniq_id,
            data=FreezeSource.MAINTENANCE.value,
        )
        application.apply_time_freeze.assert_not_called()
        application.update_incident_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_incident_updates_posted_message_when_recording_maintenance_on_frozen_incident(
        self, maintenance_setup
    ):
        manager, store, application, _ = maintenance_setup
        store.list.return_value = [_window()]
        incident = _incident()
        incident.parents.append("source-uniq-id")
        incident.ts = "1.2"

        await manager.process_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        assert incident.frozen_by_maintenance is True
        application.apply_time_freeze.assert_not_called()
        application.update_incident_message.assert_awaited_once_with(incident)

    @pytest.mark.asyncio
    async def test_reconcile_schedules_maintenance_for_inhibited_incident(self, maintenance_setup):
        manager, store, _, _ = maintenance_setup
        window = _window()
        store.list.return_value = [window]
        incident = _incident()
        incident.parents = ["source-uniq-id"]

        await manager.reconcile_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        assert incident.frozen_until == window.ends_at
        assert incident.frozen_until_source == FreezeSource.MAINTENANCE.value
        manager.queue.put.assert_awaited_once_with(
            window.ends_at,
            QueueItemType.UNFREEZE,
            incident.uniq_id,
            data=FreezeSource.MAINTENANCE.value,
        )

    @pytest.mark.asyncio
    async def test_reconcile_preserves_manual_freeze_when_maintenance_starts(self, maintenance_setup):
        manager, store, _, _ = maintenance_setup
        window = _window()
        store.list.return_value = [window]
        incident = _incident()
        manual_until = TEST_NOW + timedelta(hours=4)
        incident.frozen_until = manual_until
        incident.frozen_until_source = FreezeSource.TIME.value

        await manager.reconcile_incident(incident)

        assert MAINTENANCE_PARENT_SENTINEL in incident.parents
        assert incident.frozen_until == manual_until
        assert incident.frozen_until_source == FreezeSource.TIME.value
        manager.queue.put.assert_awaited_once_with(
            window.ends_at,
            QueueItemType.UNFREEZE,
            incident.uniq_id,
            data=FreezeSource.MAINTENANCE.value,
        )

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
    async def test_reconcile_reschedules_to_connected_matching_window_end(self, maintenance_setup):
        manager, store, _, _ = maintenance_setup
        first = _fixed_window(TEST_NOW - timedelta(hours=1), TEST_NOW + timedelta(hours=1))
        second = _fixed_window(first.ends_at, first.ends_at + timedelta(hours=2))
        store.list.return_value = [second, first]
        incident = _incident()
        incident.parents = [MAINTENANCE_PARENT_SENTINEL]
        incident.frozen_until = first.ends_at
        incident.frozen_until_source = FreezeSource.MAINTENANCE.value

        await manager.reconcile_incident(incident)

        assert incident.frozen_until == second.ends_at
        manager.queue.put.assert_awaited_once_with(
            second.ends_at,
            QueueItemType.UNFREEZE,
            incident.uniq_id,
            data=FreezeSource.MAINTENANCE.value,
        )

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

    @pytest.mark.asyncio
    async def test_reconcile_all_includes_maintenance_time_freeze_without_sentinel(self, maintenance_setup):
        manager, store, _, _ = maintenance_setup
        store.list.return_value = []
        incident = _incident()
        incident.frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        incident.frozen_until_source = FreezeSource.MAINTENANCE.value
        manager.incidents.uniq_ids = {"a": incident}

        await manager.reconcile_all()

        assert incident.frozen_until is None


def _window_dict(window_id, start, end, matchers=None, comment="work"):
    return {
        "id": window_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "matchers": matchers or ['alertname = "TestAlert"'],
        "comment": comment,
    }


class TestMaintenanceSaveSideEffects:
    def test_needs_reconcile_when_adding_future_window_only(self, maintenance_setup):
        manager, _, _, _ = maintenance_setup
        future_start = TEST_NOW + timedelta(hours=2)
        future_end = TEST_NOW + timedelta(hours=4)
        saved = [_window_dict("w1", future_start, future_end)]

        assert manager.needs_reconcile_after_save([], saved) is False

    def test_needs_reconcile_when_adding_active_window(self, maintenance_setup):
        manager, _, _, _ = maintenance_setup
        saved = [_window_dict("w1", TEST_NOW - timedelta(hours=1), TEST_NOW + timedelta(hours=1))]

        assert manager.needs_reconcile_after_save([], saved) is True

    def test_needs_reconcile_when_editing_window_times(self, maintenance_setup):
        manager, _, _, _ = maintenance_setup
        existing = [_window_dict(
            "w1",
            TEST_NOW + timedelta(hours=2),
            TEST_NOW + timedelta(hours=4),
        )]
        saved = [_window_dict(
            "w1",
            TEST_NOW + timedelta(hours=2),
            TEST_NOW + timedelta(hours=5),
        )]

        assert manager.needs_reconcile_after_save(existing, saved) is True

    def test_needs_reconcile_false_when_only_comment_changes(self, maintenance_setup):
        manager, _, _, _ = maintenance_setup
        existing = [_window_dict(
            "w1",
            TEST_NOW + timedelta(hours=2),
            TEST_NOW + timedelta(hours=4),
            comment="old",
        )]
        saved = [_window_dict(
            "w1",
            TEST_NOW + timedelta(hours=2),
            TEST_NOW + timedelta(hours=4),
            comment="new",
        )]

        assert manager.needs_reconcile_after_save(existing, saved) is False

    @pytest.mark.asyncio
    async def test_apply_save_side_effects_skips_reconcile_all_for_future_add(self, maintenance_setup):
        manager, _, _, _ = maintenance_setup
        future_start = TEST_NOW + timedelta(hours=2)
        future_end = TEST_NOW + timedelta(hours=4)
        saved = [_window_dict("w1", future_start, future_end)]

        with patch("app.maintenance.manager.MaintenanceManager.reconcile_all", AsyncMock()) as mock_reconcile_all, \
                patch("app.maintenance.manager.MaintenanceManager.reconcile_after_window_removed", AsyncMock()) as mock_removed, \
                patch("app.maintenance.manager.MaintenanceManager.schedule_window_starts", AsyncMock()) as mock_schedule, \
                patch("app.maintenance.manager.MaintenanceManager.broadcast_active_maintenance", AsyncMock()) as mock_broadcast:
            await manager.apply_save_side_effects([], saved, [])

        mock_removed.assert_not_awaited()
        mock_reconcile_all.assert_not_awaited()
        mock_schedule.assert_awaited_once()
        mock_broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_apply_save_side_effects_reconciles_removed_without_full_reconcile(
        self, maintenance_setup
    ):
        manager, _, _, _ = maintenance_setup
        deleted = [_window_dict(
            "w1",
            TEST_NOW + timedelta(hours=2),
            TEST_NOW + timedelta(hours=4),
        )]

        with patch("app.maintenance.manager.MaintenanceManager.reconcile_all", AsyncMock()) as mock_reconcile_all, \
                patch("app.maintenance.manager.MaintenanceManager.reconcile_after_window_removed", AsyncMock()) as mock_removed, \
                patch("app.maintenance.manager.MaintenanceManager.schedule_window_starts", AsyncMock()) as mock_schedule, \
                patch("app.maintenance.manager.MaintenanceManager.broadcast_active_maintenance", AsyncMock()) as mock_broadcast:
            await manager.apply_save_side_effects(deleted, [], deleted)

        mock_removed.assert_awaited_once()
        mock_reconcile_all.assert_not_awaited()
        mock_schedule.assert_awaited_once()
        mock_broadcast.assert_awaited_once()


class TestActiveWindowsPayload:
    def test_active_windows_payload_includes_owner(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        owner = Mock()
        owner.exists = True
        owner.full_name = "Dmitry Tsybus"
        owner.name = "dmitry"
        owner.username = "dmitry"

        application.users = Mock()
        application.users.get_user_by_id.return_value = owner
        application.get_user_profile_url.return_value = "https://team.example/messages/@dmitry"

        active_window = _window(
            start_offset_hours=1,
            duration_hours=2,
        )
        active_window.owner_id = "U123"
        store.list.return_value = [active_window]

        payload = manager.active_windows_payload()

        assert len(payload) == 1
        assert payload[0]["owner_id"] == "U123"
        assert payload[0]["owner_full_name"] == "Dmitry Tsybus"
        assert payload[0]["owner_url"] == "https://team.example/messages/@dmitry"
        application.get_user_profile_url.assert_called_once_with("U123", owner)

    def test_active_windows_payload_omits_owner_when_user_missing(self, maintenance_setup):
        manager, store, application, _ = maintenance_setup
        application.users = Mock()
        application.users.get_user_by_id.return_value = None

        active_window = _window(start_offset_hours=1, duration_hours=2)
        active_window.owner_id = "U123"
        store.list.return_value = [active_window]

        payload = manager.active_windows_payload()

        assert len(payload) == 1
        assert "owner_id" not in payload[0]
        assert "owner_full_name" not in payload[0]
        application.get_user_profile_url.assert_not_called()
