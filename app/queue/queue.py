import asyncio
from collections import namedtuple
from datetime import datetime
from typing import Optional, Tuple, Any

from app.logging import logger

QueueItem = namedtuple('QueueItem', ['datetime', 'type', 'incident_uuid', 'identifier', 'data'])


class AsyncQueue:
    """Async queue implementation using asyncio.Queue and priority handling"""
    
    def __init__(self, check_update: bool = False):
        # Removed unused asyncio.Queue - using _items list for priority/delayed processing
        self._items = []
        self._lock = asyncio.Lock()
        
        self._check_update = check_update

    async def put_first(self, datetime_: datetime, type_: str, incident_uuid: str = None, 
                       identifier: str = None, data: Any = None):
        """Put item at the front of the queue"""
        new_item = QueueItem(datetime_, type_, incident_uuid, identifier, data)
        async with self._lock:
            self._items.insert(0, new_item)

    async def put(self, datetime_: datetime, type_: str, incident_uuid: str = None, 
                 identifier: str = None, data: Any = None):
        """Put item in the queue with priority sorting by datetime"""
        new_item = QueueItem(datetime_, type_, incident_uuid, identifier, data)
        async with self._lock:
            self._insert_item_sorted(new_item)

    async def delete_by_id(self, uuid: str, delete_steps: bool = True, delete_status: bool = True):
        """Delete items by incident UUID"""
        async with self._lock:
            self._delete_by_id_internal(uuid, delete_steps, delete_status)

    def _delete_by_id_internal(self, uuid: str, delete_steps: bool = True, delete_status: bool = True):
        """Internal delete method that doesn't acquire lock"""
        self._items = [
            item for item in self._items
            if not (item.incident_uuid == uuid and (
                (delete_steps and item.type == 'chain_step') or
                (delete_status and item.type == 'update_status')
            ))
        ]

    async def recreate(self, status: str, uuid: str, incident_chain: list):
        """Recreate queue items for incident chain"""
        if status != 'resolved':
            new_items = []
            for i, s in enumerate(incident_chain):
                if not s['done']:
                    new_items.append(QueueItem(s['datetime'], 'chain_step', uuid, i, None))

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

    async def update(self, uuid_: str, incident_status_change: datetime, status: str):
        """Update queue for incident status change"""
        async with self._lock:
            if status == 'resolved':
                self._delete_by_id_internal(uuid_, delete_steps=True, delete_status=False)
            self._delete_by_id_internal(uuid_, delete_steps=False, delete_status=True)
            
            new_item = QueueItem(incident_status_change, 'update_status', uuid_, None, None)
            self._insert_item_sorted(new_item)

    async def get_next_ready_item(self) -> Optional[Tuple[str, str, str, Any]]:
        """Get the next item that's ready to be processed (datetime <= now)"""
        now = datetime.utcnow()
        async with self._lock:
            if self._items and self._items[0].datetime <= now:
                item = self._items.pop(0)
                # Using _items list as the source of truth for ordering and content
                return item.type, item.incident_uuid, item.identifier, item.data
        return None, None, None, None

    async def serialize(self) -> list:
        """Serialize queue items for API response"""
        async with self._lock:
            # Create a copy to avoid holding the lock too long
            items_copy = self._items.copy()
        
        return [
            {
                'datetime': item.datetime,
                'type': item.type,
                'incident_uuid': item.incident_uuid,
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

    @classmethod
    async def recreate_queue(cls, incidents, check_update: bool):
        """Recreate queue from existing incidents"""
        logger.info('Creating AsyncQueue')
        queue = cls(check_update)

        if check_update:
            check_update_datetime = datetime.utcnow()
            await queue.put(check_update_datetime, 'check_update', None, 'first')

        for uuid_, incident in incidents.by_uuid.items():
            await queue.recreate(incident.status, uuid_, incident.get_chain())
            await queue.put(incident.status_update_datetime, 'update_status', uuid_)

        return queue
