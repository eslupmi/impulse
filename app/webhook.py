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
    def __init__(self, url, data=None, json_payload=None, auth=None):
        self._url = self.render(url)
        self._pre_render_data = data
        self._json_payload = json_payload
        self._auth = auth

    async def push(self, incident: Incident = None, session: aiohttp.ClientSession = None):
        rendered_data = self._render_data(incident)
        rendered_json = self._render_json(incident)
        auth = self._get_auth() if self._auth else None

        # Use provided session or create a temporary one
        if session:
            return await self._make_request(session, rendered_data, rendered_json, auth)
        else:
            async with aiohttp.ClientSession() as temp_session:
                return await self._make_request(temp_session, rendered_data, rendered_json, auth)

    async def _make_request(self, session: aiohttp.ClientSession, rendered_data, rendered_json, auth):
        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            
            # Determine whether to send as JSON or form data
            if rendered_json is not None:
                if isinstance(rendered_json, str):
                    # If it's a string, send as raw JSON text
                    logger.debug(f'Sending webhook JSON string to {self._url}: {rendered_json}')
                    async with session.post(
                            url=self._url,
                            data=rendered_json,
                            headers={'Content-Type': 'application/json'},
                            auth=auth,
                            timeout=timeout
                    ) as response:
                        return 'ok', response.status
                else:
                    # If it's a dict, use json parameter
                    logger.debug(f'Sending webhook JSON dict to {self._url}: {rendered_json}')
                    async with session.post(
                            url=self._url,
                            json=rendered_json,
                            auth=auth,
                            timeout=timeout
                    ) as response:
                        return 'ok', response.status
            else:
                logger.debug(f'Sending webhook form data to {self._url}: {rendered_data}')
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

    def _render_json(self, incident: Incident = None):
        if not self._json_payload:
            return None
            
        if isinstance(self._json_payload, str):
            # If json_payload is a string, render it as a template
            serialized_incident = incident.serialize() if incident else dict()
            return self.render(self._json_payload, incident=serialized_incident)
        else:
            # If json_payload is a dict, render recursively
            serialized_incident = incident.serialize() if incident else dict()
            return self._render_nested_dict(self._json_payload, serialized_incident)

    def _render_nested_dict(self, data, incident_data):
        """
        Recursively render nested dictionaries and lists with Jinja2 templates.
        
        Args:
            data: Dictionary or list to render
            incident_data: Serialized incident data for template context
            
        Returns:
            Rendered data structure
        """
        if isinstance(data, dict):
            rendered_dict = {}
            for key, value in data.items():
                rendered_dict[key] = self._render_nested_dict(value, incident_data)
            return rendered_dict
        elif isinstance(data, list):
            rendered_list = []
            for item in data:
                rendered_list.append(self._render_nested_dict(item, incident_data))
            return rendered_list
        elif isinstance(data, str):
            # Render string values as Jinja2 templates
            return self.render(data, incident=incident_data)
        else:
            # Return primitive values as-is (int, float, bool, None)
            return data

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
            json_payload = webhook_obj.json_payload
            auth = webhook_obj.auth
            webhooks[name] = Webhook(url, data, json_payload, auth)
    return webhooks
