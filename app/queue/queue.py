import asyncio
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Any

from app.logging import logger
from app.queue.constants import QueueItemType

QueueItem = namedtuple('QueueItem', ['datetime', 'type', 'uniq_id', 'identifier', 'data'])


class AsyncQueue:
    """Async queue implementation using asyncio.Queue and priority handling"""
    
    def __init__(self):
        self._items = []
        self._lock = asyncio.Lock()

    async def put_first(self, datetime_: datetime, type_: str, uniq_id: str = None,
                       identifier: str = None, data: Any = None):
        """Put item at the front of the queue"""
        new_item = QueueItem(datetime_, type_, uniq_id, identifier, data)
        async with self._lock:
            self._items.insert(0, new_item)

    async def put(self, datetime_: datetime, type_: str, uniq_id: str = None,
                 identifier: str = None, data: Any = None):
        """Put item in the queue with priority sorting by datetime"""
        new_item = QueueItem(datetime_, type_, uniq_id, identifier, data)
        async with self._lock:
            self._insert_item_sorted(new_item)

    async def delete_by_id(self, uniq_id: str, delete_steps: bool = True, delete_status: bool = True):
        """Delete items by incident uniq_id"""
        async with self._lock:
            self._delete_by_id_internal(uniq_id, delete_steps, delete_status)
    
    async def delete_by_id_and_type(self, uniq_id: str, type_: str):
        """Delete items by incident uniq_id and type"""
        async with self._lock:
            self._delete_by_id_and_type_internal(uniq_id, type_)

    def _delete_by_id_internal(self, uniq_id: str, delete_steps: bool = True, delete_status: bool = True):
        """Internal delete method that doesn't acquire lock"""
        self._items = [
            item for item in self._items
            if not (item.uniq_id == uniq_id and (
                (delete_steps and item.type == QueueItemType.CHAIN_STEP) or
                (delete_status and item.type == QueueItemType.UPDATE_STATUS)
            ))
        ]

    def _delete_by_id_and_type_internal(self, uniq_id: str, type_: str):
        """Internal delete by id and type method that doesn't acquire lock"""
        self._items = [
            item for item in self._items
            if not (item.uniq_id == uniq_id and item.type == type_)
        ]

    async def recreate(self, status: str, uniq_id: str, incident_chain: list, chain_active_seconds: float = 0.0):
        """Recreate queue items for incident chain using relative seconds"""
        if status == 'firing' or status == 'unknown':
            now = datetime.now(timezone.utc)
            new_items = []
            for i, s in enumerate(incident_chain):
                if not s['done']:
                    remaining = s['delay'] - chain_active_seconds
                    schedule_at = now + timedelta(seconds=max(0, remaining))
                    new_items.append(QueueItem(schedule_at, QueueItemType.CHAIN_STEP, uniq_id, i, None))

            async with self._lock:
                for new_item in new_items:
                    self._insert_item_sorted(new_item)

    def _insert_item_sorted(self, new_item: QueueItem):
        """Insert item in sorted order by datetime"""
        for i, item in enumerate(self._items):
            if new_item.datetime < item.datetime:
                self._items.insert(i, new_item)
                return
        self._items.append(new_item)

    async def update(self, uniq_id: str, incident_status_change: datetime, status: str):
        """Update queue for incident status change"""
        async with self._lock:
            if status == 'resolved':
                self._delete_by_id_internal(uniq_id, delete_steps=True, delete_status=False)
            self._delete_by_id_internal(uniq_id, delete_steps=False, delete_status=True)
            
            new_item = QueueItem(incident_status_change, QueueItemType.UPDATE_STATUS, uniq_id, None, None)
            self._insert_item_sorted(new_item)

    async def get_next_ready_item(self) -> Optional[Tuple[str, str, str, Any]]:
        """Get the next item that's ready to be processed (datetime <= now)"""
        now = datetime.now(timezone.utc)
        async with self._lock:
            if self._items and self._items[0].datetime <= now:
                item = self._items.pop(0)
                # Using _items list as the source of truth for ordering and content
                return item.type, item.uniq_id, item.identifier, item.data
        return "", "", "", {}

    async def get_first_item_datetime(self) -> Optional[datetime]:
        """Get datetime of the next item that's ready to be processed (if any)."""
        async with self._lock:
            if self._items:
                return self._items[0].datetime
        return None

    async def serialize(self) -> list:
        """Serialize queue items for API response"""
        async with self._lock:
            # Create a copy to avoid holding the lock too long
            items_copy = self._items.copy()
        
        return [
            {
                'datetime': item.datetime,
                'type': item.type,
                'uniq_id': item.uniq_id,
                'identifier': item.identifier
            } for item in items_copy
        ]

    @property
    def items(self) -> list:
        """Get current items (for compatibility) - WARNING: Not thread-safe, use len() for count checks"""
        return self._items
    
    async def get_items_count(self) -> int:
        """Get count of items safely"""
        async with self._lock:
            return len(self._items)

    async def get_latest_item_by_type(self, type_: str) -> Optional[datetime]:
        """Get the datetime of the latest scheduled item of a specific type."""
        async with self._lock:
            latest = None
            for item in self._items:
                if item.type == type_:
                    if latest is None or item.datetime > latest:
                        latest = item.datetime
            return latest

    @classmethod
    async def recreate_queue(cls, incidents):
        """Recreate queue from existing incidents"""
        logger.info('Creating Queue')
        queue = cls()

        for uniq_id, incident in incidents.uniq_ids.items():
            if incident.is_frozen() and incident.frozen_until:
                await queue.put(incident.frozen_until, QueueItemType.UNFREEZE, uniq_id)
            elif not incident.is_frozen():
                await queue.recreate(incident.status, uniq_id, incident.get_chain(), incident.chain_active_seconds)
            if incident.status != 'deleted':
                await queue.put(incident.status_update_datetime, QueueItemType.UPDATE_STATUS, uniq_id)
            else:
                await queue.put_first(datetime.now(timezone.utc), QueueItemType.STATUS_CHECK, uniq_id)

        return queue
