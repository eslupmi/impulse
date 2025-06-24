from datetime import datetime, timedelta
import asyncio

import aiohttp

from app.queue.handlers.base_handler import BaseHandler


class UpdateHandler(BaseHandler):
    """
    UpdateHandler class is responsible for handling the update check.

    :param queue: AsyncQueue instance
    :param application: Application instance
    :param incidents: Incidents instance
    """
    __slots__ = ['queue', 'app', 'incidents', 'latest_tag']

    def __init__(self, queue, application, incidents):
        super().__init__(queue, application, incidents)
        self.latest_tag = {'version': None}

    async def handle(self, identifier):
        current_tag = await get_latest_tag()
        if identifier != 'first' and current_tag != self.latest_tag['version']:
            await self.app.new_version_notification(self.app.default_channel_id, current_tag)
            self.latest_tag['version'] = current_tag
        elif identifier == 'first':
            self.latest_tag['version'] = current_tag

        # Always schedule the next check update
        await self.queue.put(datetime.utcnow() + timedelta(days=1), 'check_update', None, identifier=None)


async def get_latest_tag():
    """Get the latest tag from GitHub API"""
    try:
        timeout = aiohttp.ClientTimeout(total=5.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('https://api.github.com/repos/impulse-project/impulse/releases/latest') as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('tag_name', 'unknown')
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    return 'unknown'
