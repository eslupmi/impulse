from datetime import datetime, timedelta, timezone

from app.im.user_store import USER_REFRESH_HOURS, get_user_store
from app.logging import logger
from app.queue.constants import USER_UPDATE_GAP_SECONDS, QueueItemType
from app.queue.handlers.base_handler import BaseHandler


class UserUpdateHandler(BaseHandler):
    """Handle user data refresh via messenger API and persist to UserStore."""
    __slots__: list[str] = []

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
            config_name = self.app.get_config_name_by_user_id(user_id)
            user = self.app.create_user(config_name, user_details)
            if user and self.app.users:
                self.app._apply_admin_role(user, config_name)
                self.app.users.add_user(user_id, user, config_name=config_name)
            logger.info('User data refreshed', extra={'user_id': user_id})
        except Exception as e:  # noqa: BLE001
            logger.error('Failed to update user', extra={'user_id': user_id, 'error': str(e)})
        await self._schedule_next_refresh(user_id)

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
