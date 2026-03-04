import asyncio
import os
from typing import Dict

import aiohttp
from aiohttp import BasicAuth, ClientTimeout
from aiohttp_retry import ExponentialRetry, RetryClient
from jinja2 import Template

from app.config.validation import WebhookConfig
from app.incident.incident import Incident
from app.logging import logger


class Webhook:
    def __init__(self, url, data=None, json_payload=None, auth=None):
        self._url = self.render(url)
        self._data = data
        self._json_payload = json_payload
        self._auth = auth

    async def push(self, incident: Incident = None):
        rendered_data = self._render_data(incident)
        rendered_json = self._render_json(incident)
        auth = self._get_auth() if self._auth else None

        retry_options = ExponentialRetry(
            attempts=3,
            start_timeout=1.0,
            max_timeout=10.0,
            statuses={500, 502, 503, 504}
        )
        timeout = ClientTimeout(total=30.0)
        async with aiohttp.ClientSession(timeout=timeout) as temp_session:
            retry_client = RetryClient(client_session=temp_session, retry_options=retry_options)
            return await self._make_request(retry_client, rendered_data, rendered_json, auth)

    async def _make_request(self, session, rendered_data, rendered_json, auth):
        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            request_params = {
                'url': self._url,
                'auth': auth,
                'timeout': timeout
            }
            
            # Determine request type and parameters
            if rendered_json is not None:
                if isinstance(rendered_json, str):
                    request_params.update({
                        'data': rendered_json,
                        'headers': {'Content-Type': 'application/json'}
                    })
                else:
                    request_params['json'] = rendered_json
            else:
                request_params['data'] = rendered_data
            
            logger.debug(f'Sending webhook to {self._url}')
            
            async with session.post(**request_params) as response:
                return 'ok', response.status
                
        except asyncio.TimeoutError:
            return 'Timeout', None
        except aiohttp.ClientConnectionError:
            return 'ConnectionError', None
        except aiohttp.ClientError as e:
            logger.error(f'Webhook request failed: {e}')
            return 'ClientError', None

    ### private methods ###
    def _render_data(self, incident: Incident = None):
        rendered_data = {}
        if self._data:
            serialized_incident = incident.serialize() if incident else {}
            for key, value in self._data.items():
                rendered_data[key] = self.render(value, incident=serialized_incident)
        return rendered_data

    def _render_json(self, incident: Incident = None):
        if not self._json_payload:
            return None
            
        if isinstance(self._json_payload, str):
            # If json_payload is a string, render it as a template
            serialized_incident = incident.serialize() if incident else {}
            return self.render(self._json_payload, incident=serialized_incident)
        else:
            # If json_payload is a dict, render recursively
            serialized_incident = incident.serialize() if incident else {}
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
            return self.render(data, incident=incident_data)
        else:
            return data

    def _get_auth(self):
        u, p = self._auth.split(':')
        return BasicAuth(self.render(u), self.render(p))

    @staticmethod
    def render(custom_string, **kwargs):
        tmplt = Template(custom_string)
        return tmplt.render(env=os.environ, **kwargs)


def generate_webhooks(webhooks_config: Dict[str, WebhookConfig] = None):
    webhooks = {}
    if webhooks_config:
        for name in webhooks_config.keys():
            webhook_obj = webhooks_config[name]
            url = webhook_obj.url
            data = webhook_obj.data
            json_payload = webhook_obj.json_payload
            auth = webhook_obj.auth
            webhooks[name] = Webhook(url, data, json_payload, auth)
    return webhooks
