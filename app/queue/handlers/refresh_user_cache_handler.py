from datetime import datetime, timedelta, timezone
from typing import Optional, Set

from app.cache.chain_utils import extract_user_ids_from_route
from app.cache.user_cache import UserCache
from app.logging import logger
from app.queue.handlers.base_handler import BaseHandler

class RefreshUserCacheHandler(BaseHandler):
    """
    Handler for refreshing user cache.
    Fetches user details from API and updates cache.
    """
    
    def __init__(self, queue, application, incidents, route_):
        super().__init__(queue, application, incidents)
        self.route = route_
    
    async def handle(self, user_ids: Optional[Set[str]]) -> None:
        """
        Refresh cache for specified user IDs.
        If user_ids is None, refreshes all users from route data.
        
        Args:
            user_ids: Set of user IDs to refresh, or None to refresh all
        """
        if user_ids is None:            
            if self.route and self.app.users and self.app.user_groups:
                user_ids = extract_user_ids_from_route(
                    self.route,
                    self.app.chains,
                    self.app.users,
                    self.app.user_groups
                )
            else:
                logger.warning("Cannot extract user IDs from route: missing route, users, or user_groups")
                return
        
        if not user_ids:
            logger.info("No user IDs to refresh")
            return
        
        cache = UserCache()
        refreshed_count = 0
        failed_count = 0
        
        logger.info(f"Refreshing cache for {len(user_ids)} users")
        
        for user_id in user_ids:
            try:
                # Fetch user details from API
                user_details = await self.app.get_user_details({'id': user_id})
                
                if user_details.get('exists'):
                    cache.set(user_id, user_details)
                    refreshed_count += 1
                    logger.debug(f"Refreshed cache for user {user_id}")
                else:
                    logger.debug(f"User {user_id} does not exist, skipping cache update")
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to refresh cache for user {user_id}: {e}")
                failed_count += 1
        
        logger.info(f"Cache refresh completed: {refreshed_count} refreshed, {failed_count} failed")
        
        # Schedule next refresh in 12 hours
        next_refresh_time = datetime.now(timezone.utc) + timedelta(hours=12)
        await self.queue.put(
            datetime_=next_refresh_time,
            type_='refresh_user_cache',
        )
        logger.debug(f"Scheduled next cache refresh at {next_refresh_time}")
