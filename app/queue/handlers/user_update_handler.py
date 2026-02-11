from datetime import datetime, timezone, timedelta

from app.im.user_store import get_user_store, USER_REFRESH_HOURS
from app.logging import logger
from app.queue.constants import QueueItemType, USER_UPDATE_GAP_SECONDS
from app.queue.handlers.base_handler import BaseHandler


class UserUpdateHandler(BaseHandler):
    """Handle user data refresh via messenger API and persist to UserStore."""
    __slots__ = []

    async def handle(self, user_id: str):
        if not user_id:
            logger.warning('UserUpdateHandler called with empty user_id')
            return

        user_store = get_user_store()
        messenger_type = self.app.type.value
        
        try:
            user_details = await self.app.get_user_details({'id': user_id})
            
            if not user_details.get('exists'):
                logger.debug('User not found in messenger, skipping storage', extra={'user_id': user_id})
                await self._schedule_next_refresh(user_id)
                return
            
            user_store.save(user_id, messenger_type, user_details)
            self._update_user_manager(user_id, user_details)
            logger.info('User data refreshed', extra={'user_id': user_id})
            
        except Exception as e:
            logger.error('Failed to update user', extra={'user_id': user_id, 'error': str(e)})
        
        await self._schedule_next_refresh(user_id)

    def _update_user_manager(self, user_id: str, user_details: dict):
        """Update the user in UserManager with fresh data."""
        display_name = self.app.format_display_name(user_details)
        user = self.app.create_user(display_name, user_details)
        if user:
            self.app.users.add_user(user_id, user)

    async def _schedule_next_refresh(self, user_id: str):
        """Schedule next refresh with proper gap from latest UPDATE_USER item."""
        gap_seconds = USER_UPDATE_GAP_SECONDS.get(self.app.type.value, 1.0)
        latest = await self.queue.get_latest_item_by_type(QueueItemType.UPDATE_USER)
        
        now = datetime.now(timezone.utc)
        next_refresh_base = now + timedelta(hours=USER_REFRESH_HOURS)
        
        if latest and latest > next_refresh_base:
            schedule_time = latest + timedelta(seconds=gap_seconds)
        else:
            schedule_time = next_refresh_base
        
        await self.queue.put(schedule_time, QueueItemType.UPDATE_USER, identifier=str(user_id))
