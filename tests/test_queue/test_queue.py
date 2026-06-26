"""
Unit tests for app.queue.queue module.
"""
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest

from app.queue.queue import AsyncQueue, QueueItem
from tests.utils import create_test_datetime, create_alert_payload, create_mock_incidents_collection


class TestQueueItem:
    """Test cases for QueueItem namedtuple."""

    def test_queue_item_creation(self):
        """Test creating QueueItem."""
        dt = create_test_datetime()
        item = QueueItem(dt, 'test_type', 'incident123', 'identifier456', {'data': 'test'})

        assert item.datetime == dt
        assert item.type == 'test_type'
        assert item.uniq_id == 'incident123'
        assert item.identifier == 'identifier456'
        assert item.data == {'data': 'test'}

    def test_queue_item_creation_with_none_values(self):
        """Test creating QueueItem with None values."""
        dt = create_test_datetime()
        item = QueueItem(dt, 'test_type', None, None, None)

        assert item.datetime == dt
        assert item.type == 'test_type'
        assert item.uniq_id is None
        assert item.identifier is None
        assert item.data is None


class TestAsyncQueue:
    """Test cases for AsyncQueue class."""

    @pytest.fixture
    def queue(self):
        """Create AsyncQueue instance for testing."""
        return AsyncQueue()

    @pytest.mark.asyncio
    async def test_put_item(self, queue):
        """Test putting item in queue."""
        dt = create_test_datetime()
        test_data = create_alert_payload()

        await queue.put(dt, 'test_type', 'incident123', 'identifier456', test_data)

        assert len(queue._items) == 1
        item = queue._items[0]
        assert item.datetime == dt
        assert item.type == 'test_type'
        assert item.uniq_id == 'incident123'
        assert item.identifier == 'identifier456'
        assert item.data == test_data

    @pytest.mark.asyncio
    async def test_put_first_item(self, queue):
        """Test putting item at front of queue."""
        dt1 = create_test_datetime()
        dt2 = dt1 + timedelta(seconds=10)

        # Add item normally
        await queue.put(dt2, 'normal_type', 'incident1', 'id1', None)

        # Add item at front
        await queue.put_first(dt1, 'priority_type', 'incident2', 'id2', None)

        assert len(queue._items) == 2
        assert queue._items[0].type == 'priority_type'  # Should be first
        assert queue._items[1].type == 'normal_type'

    @pytest.mark.asyncio
    async def test_put_items_sorted_by_datetime(self, queue):
        """Test that items are sorted by datetime when added."""
        base_time = create_test_datetime()

        # Add items in reverse chronological order
        await queue.put(base_time + timedelta(seconds=30), 'type3', 'incident3', 'id3', None)
        await queue.put(base_time + timedelta(seconds=10), 'type1', 'incident1', 'id1', None)
        await queue.put(base_time + timedelta(seconds=20), 'type2', 'incident2', 'id2', None)

        assert len(queue._items) == 3
        # Should be sorted by datetime
        assert queue._items[0].type == 'type1'  # Earliest
        assert queue._items[1].type == 'type2'
        assert queue._items[2].type == 'type3'  # Latest

    @pytest.mark.asyncio
    async def test_delete_by_id_steps_and_status(self, queue):
        """Test deleting items by UUID for both steps and status."""
        dt = create_test_datetime()

        # Add items of different types
        await queue.put(dt, 'chain_step', 'incident123', '0', None)
        await queue.put(dt, 'update_status', 'incident123', None, None)
        await queue.put(dt, 'chain_step', 'incident456', '1', None)  # Different UUID

        await queue.delete_by_id('incident123', delete_steps=True, delete_status=True)

        assert len(queue._items) == 1
        assert queue._items[0].uniq_id == 'incident456'

    @pytest.mark.asyncio
    async def test_delete_by_id_steps_only(self, queue):
        """Test deleting items by UUID for steps only."""
        dt = create_test_datetime()

        await queue.put(dt, 'chain_step', 'incident123', '0', None)
        await queue.put(dt, 'update_status', 'incident123', None, None)

        await queue.delete_by_id('incident123', delete_steps=True, delete_status=False)

        assert len(queue._items) == 1
        assert queue._items[0].type == 'update_status'

    @pytest.mark.asyncio
    async def test_delete_by_id_status_only(self, queue):
        """Test deleting items by UUID for status only."""
        dt = create_test_datetime()

        await queue.put(dt, 'chain_step', 'incident123', '0', None)
        await queue.put(dt, 'update_status', 'incident123', None, None)

        await queue.delete_by_id('incident123', delete_steps=False, delete_status=True)

        assert len(queue._items) == 1
        assert queue._items[0].type == 'chain_step'

    @pytest.mark.asyncio
    async def test_delete_by_id_nonexistent_uuid(self, queue):
        """Test deleting items with non-existent UUID."""
        dt = create_test_datetime()

        await queue.put(dt, 'chain_step', 'incident123', '0', None)

        await queue.delete_by_id('nonexistent', delete_steps=True, delete_status=True)

        assert len(queue._items) == 1  # Should remain unchanged

    @pytest.mark.asyncio
    async def test_delete_by_type(self, queue):
        """Test deleting all items of one type."""
        dt = create_test_datetime()
        await queue.put(dt, 'maintenance_start', None, 'w1', None)
        await queue.put(dt, 'maintenance_start', None, 'w2', None)
        await queue.put(dt, 'update_status', 'incident123', None, None)

        await queue.delete_by_type('maintenance_start')

        assert len(queue._items) == 1
        assert queue._items[0].type == 'update_status'

    @pytest.mark.asyncio
    async def test_delete_by_id_type_and_data(self, queue):
        """Test deleting only queue items matching id, type, and data."""
        dt = create_test_datetime()
        await queue.put(dt, 'unfreeze', 'incident123', None, 'maintenance')
        await queue.put(dt, 'unfreeze', 'incident123', None, 'time')
        await queue.put(dt, 'unfreeze', 'incident456', None, 'maintenance')

        await queue.delete_by_id_type_and_data('incident123', 'unfreeze', 'maintenance')

        assert len(queue._items) == 2
        assert {item.data for item in queue._items} == {'time', 'maintenance'}
        assert any(item.uniq_id == 'incident456' for item in queue._items)

    @pytest.mark.asyncio
    async def test_recreate_resolved_status(self, queue):
        """Test recreate with resolved status (should not add items)."""
        incident_chain = [
            {'done': False, 'delay': 300.0},
            {'done': True, 'delay': 600.0},
            {'done': False, 'delay': 900.0}
        ]

        await queue.recreate('resolved', 'incident123', incident_chain)

        assert len(queue._items) == 0

    @pytest.mark.asyncio
    async def test_recreate_non_resolved_status(self, queue):
        """Test recreate with non-resolved status (should add items)."""
        incident_chain = [
            {'done': False, 'delay': 300.0, 'type': 'step1'},
            {'done': True, 'delay': 600.0, 'type': 'step2'},
            {'done': False, 'delay': 900.0, 'type': 'step3'}
        ]

        await queue.recreate('firing', 'incident123', incident_chain)

        assert len(queue._items) == 2  # Only non-done items
        assert queue._items[0].uniq_id == 'incident123'
        assert queue._items[0].identifier == 0
        assert queue._items[1].uniq_id == 'incident123'
        assert queue._items[1].identifier == 2

    @pytest.mark.asyncio
    async def test_update_resolved_status(self, queue):
        """Test update with resolved status."""
        dt = create_test_datetime()

        # Add some existing items
        await queue.put(dt, 'chain_step', 'incident123', '0', None)
        await queue.put(dt, 'update_status', 'incident123', None, None)

        new_dt = dt + timedelta(minutes=5)
        await queue.update('incident123', new_dt, 'resolved')

        # Should delete steps but not status, then add new status
        assert len(queue._items) == 1
        assert queue._items[0].type == 'update_status'
        assert queue._items[0].uniq_id == 'incident123'

    @pytest.mark.asyncio
    async def test_update_non_resolved_status(self, queue):
        """Test update with non-resolved status."""
        dt = create_test_datetime()

        # Add some existing items
        await queue.put(dt, 'chain_step', 'incident123', '0', None)
        await queue.put(dt, 'update_status', 'incident123', None, None)

        new_dt = dt + timedelta(minutes=5)
        await queue.update('incident123', new_dt, 'firing')

        # Should delete status but keep steps, then add new status
        assert len(queue._items) == 2
        assert queue._items[0].type == 'chain_step'  # Step should remain
        assert queue._items[1].type == 'update_status'  # New status
        assert queue._items[1].uniq_id == 'incident123'

    @pytest.mark.asyncio
    async def test_get_next_ready_item_ready(self, queue):
        """Test getting next ready item when item is ready."""
        past_time = create_test_datetime() - timedelta(minutes=1)

        await queue.put(past_time, 'test_type', 'incident123', 'identifier456', {'data': 'test'})

        item_type, uniq_id, identifier, data = await queue.get_next_ready_item()

        assert item_type == 'test_type'
        assert uniq_id == 'incident123'
        assert identifier == 'identifier456'
        assert data == {'data': 'test'}
        assert len(queue._items) == 0  # Item should be removed


    @pytest.mark.asyncio
    async def test_serialize(self, queue):
        """Test serializing queue items."""
        dt = create_test_datetime()

        await queue.put(dt, 'test_type', 'incident123', 'identifier456', {'data': 'test'})
        await queue.put(dt + timedelta(minutes=1), 'another_type', 'incident456', 'identifier789', None)

        serialized = await queue.serialize()

        assert len(serialized) == 2
        assert serialized[0]['type'] == 'test_type'
        assert serialized[0]['uniq_id'] == 'incident123'
        assert serialized[0]['identifier'] == 'identifier456'
        assert serialized[1]['type'] == 'another_type'
        assert serialized[1]['uniq_id'] == 'incident456'
        assert serialized[1]['identifier'] == 'identifier789'

    @pytest.mark.asyncio
    async def test_serialize_empty_queue(self, queue):
        """Test serializing empty queue."""
        serialized = await queue.serialize()

        assert serialized == []

    @pytest.mark.asyncio
    async def test_concurrent_access(self, queue):
        """Test concurrent access to queue."""
        dt = create_test_datetime()

        # Simulate concurrent access
        import asyncio

        async def add_item(delay, item_type, uniq_id):
            await asyncio.sleep(delay)
            await queue.put(dt, item_type, uniq_id, 'id', None)

        # Add items concurrently
        tasks = [
            add_item(0.01, 'type1', 'incident1'),
            add_item(0.02, 'type2', 'incident2'),
            add_item(0.03, 'type3', 'incident3')
        ]

        await asyncio.gather(*tasks)

        assert len(queue._items) == 3

    @pytest.mark.asyncio
    async def test_insert_item_sorted_edge_cases(self, queue):
        """Test _insert_item_sorted with edge cases."""
        base_time = create_test_datetime()

        # Test inserting at the beginning
        await queue.put(base_time + timedelta(seconds=30), 'type3', 'incident3', 'id3', None)
        await queue.put(base_time + timedelta(seconds=10), 'type1', 'incident1', 'id1', None)

        # Test inserting at the end
        await queue.put(base_time + timedelta(seconds=50), 'type4', 'incident4', 'id4', None)

        # Test inserting in the middle
        await queue.put(base_time + timedelta(seconds=20), 'type2', 'incident2', 'id2', None)

        assert len(queue._items) == 4
        assert queue._items[0].type == 'type1'  # Earliest
        assert queue._items[1].type == 'type2'
        assert queue._items[2].type == 'type3'
        assert queue._items[3].type == 'type4'  # Latest

    @pytest.mark.asyncio
    async def test_delete_by_id_internal_edge_cases(self, queue):
        """Test _delete_by_id_internal with edge cases."""
        dt = create_test_datetime()

        # Add items with different types and UUIDs
        await queue.put(dt, 'chain_step', 'incident123', '0', None)
        await queue.put(dt, 'update_status', 'incident123', None, None)
        await queue.put(dt, 'chain_step', 'incident456', '1', None)
        await queue.put(dt, 'other_type', 'incident123', 'other', None)

        # Delete only steps for incident123
        queue._delete_by_id_internal('incident123', delete_steps=True, delete_status=False)

        assert len(queue._items) == 3  # Should remove 1 chain_step
        remaining_types = [item.type for item in queue._items]
        assert 'chain_step' in remaining_types  # incident456's step should remain
        assert 'update_status' in remaining_types
        assert 'other_type' in remaining_types

    @pytest.mark.asyncio
    async def test_get_items_count(self, queue):
        """Test getting items count safely."""
        dt = create_test_datetime()

        # Initially empty
        count = await queue.get_items_count()
        assert count == 0

        # Add some items
        await queue.put(dt, 'type1', 'incident1', 'id1', None)
        await queue.put(dt + timedelta(seconds=1), 'type2', 'incident2', 'id2', None)

        count = await queue.get_items_count()
        assert count == 2

    def test_items_property(self, queue):
        """Test items property access."""
        dt = create_test_datetime()

        # Add items directly to _items (bypassing async methods for testing)
        queue._items.append(QueueItem(dt, 'type1', 'incident1', 'id1', None))
        queue._items.append(QueueItem(dt + timedelta(seconds=1), 'type2', 'incident2', 'id2', None))

        items = queue.items
        assert len(items) == 2
        assert items[0].type == 'type1'
        assert items[1].type == 'type2'

    @pytest.mark.asyncio
    async def test_recreate_queue_class_method(self):
        """Test recreate_queue class method."""
        # Create mock incidents collection
        mock_incidents = Mock()
        
        # Create mock incidents with chains
        incident1 = Mock()
        incident1.status = 'firing'
        incident1.is_frozen.return_value = False
        incident1.chain_active_seconds = 0.0
        incident1.get_chain.return_value = [
            {'done': False, 'delay': 300.0},
            {'done': True, 'delay': 600.0},
            {'done': False, 'delay': 900.0}
        ]
        incident1.status_update_datetime = create_test_datetime()

        incident2 = Mock()
        incident2.status = 'resolved'
        incident2.is_frozen.return_value = False
        incident2.chain_active_seconds = 0.0
        incident2.get_chain.return_value = [
            {'done': True, 'delay': 300.0},
            {'done': True, 'delay': 600.0}
        ]
        incident2.status_update_datetime = create_test_datetime()
        
        # Set up uniq_ids as a dictionary
        mock_incidents.uniq_ids = {
            'uniq_id1': incident1,
            'uniq_id2': incident2
        }

        with patch('app.queue.queue.logger') as mock_logger:
            queue = await AsyncQueue.recreate_queue(mock_incidents)

            # Should have logged the creation
            mock_logger.info.assert_called_once_with('Creating Queue')

            # Should have items for both incidents:
            # - incident1 (firing): 2 chain steps + 1 status update = 3 items
            # - incident2 (resolved): 1 status update = 1 item
            # Total: 4 items
            count = await queue.get_items_count()
            assert count == 4
