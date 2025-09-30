import asyncio
import os
from typing import Dict

import aiohttp
from aiohttp import BasicAuth
from jinja2 import Template

from app.config.validation import WebhookConfig
from app.incident.incident import Incident
from app.logging import logger


class Webhook:
    def __init__(self, url, data=None, auth=None):
        self._url = self.render(url)
        self._pre_render_data = data
        self._auth = auth

    async def push(self, incident: Incident = None, session: aiohttp.ClientSession = None):
        rendered_data = self._render_data(incident)
        auth = self._get_auth() if self._auth else None

        # Use provided session or create a temporary one
        if session:
            return await self._make_request(session, rendered_data, auth)
        else:
            async with aiohttp.ClientSession() as temp_session:
                return await self._make_request(temp_session, rendered_data, auth)

    async def _make_request(self, session: aiohttp.ClientSession, rendered_data, auth):
        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            async with session.post(
                    url=self._url,
                    data=rendered_data,
                    auth=auth,
                    timeout=timeout
            ) as response:
                return 'ok', response.status
        except asyncio.TimeoutError:
            return 'Timeout', None
        except aiohttp.ClientConnectionError:
            return 'ConnectionError', None
        except aiohttp.ClientError as e:
            logger.error(f'Webhook request failed: {e}')
            return 'ClientError', None

    def _render_data(self, incident: Incident = None):
        rendered_data = dict()
        if self._pre_render_data:
            serialized_incident = incident.serialize() if incident else dict()
            for key, value in self._pre_render_data.items():
                rendered_data[key] = self.render(value, incident=serialized_incident)
        return rendered_data

    def _get_auth(self):
        u, p = self._auth.split(':')
        return BasicAuth(self.render(u), self.render(p))

    @staticmethod
    def render(custom_string, **kwargs):
        tmplt = Template(custom_string)
        return tmplt.render(env=os.environ, **kwargs)


def generate_webhooks(webhooks_config: Dict[str, WebhookConfig] = None):
    webhooks = dict()
    if webhooks_config:
        for name in webhooks_config.keys():
            webhook_obj = webhooks_config[name]
            url = webhook_obj.url
            data = webhook_obj.data
            auth = webhook_obj.auth
            webhooks[name] = Webhook(url, data, auth)
    return webhooks
