from app.im.colors import status_colors
from app.im.mattermost.config import buttons
from app.config.config import get_config


def chain_attrs(chain_enabled, status):
    if chain_enabled:
        chain_text = buttons['chain']['takeit']['text']
        chain_style = buttons['chain']['takeit']['style']
    else:
        if status != 'resolved':
            chain_text = buttons['chain']['assigned']['text']
            chain_style = buttons['chain']['assigned']['style']
        else:
            chain_text = buttons['chain']['release']['text']
            chain_style = buttons['chain']['release']['style']
    return chain_text, chain_style


def mattermost_get_button_update_payload(body, header, status_icons, status, chain_enabled, status_enabled):
    config = get_config()
    payload = {
        'update': {
            'message': f'{status_icons} {header}',
            'props': {
                'attachments': [
                    {
                        'fallback': 'test',
                        'text': body,
                        'color': status_colors.get(status),
                        'actions': [
                            {
                                "id": "chain",
                                "type": "button",
                                "name": chain_attrs(chain_enabled, status)[0],
                                "style": chain_attrs(chain_enabled, status)[1],
                                "integration": {
                                    "url": f"{config.application.impulse_address}/app",
                                    "context": {
                                        "action": "chain"
                                    }
                                }
                            },
                            {
                                "id": "status",
                                "type": "button",
                                "name": buttons['status']['enabled']['text'] if status_enabled else
                                buttons['status']['disabled']['text'],
                                "style": buttons['status']['enabled']['style'] if status_enabled else
                                buttons['status']['disabled']['style'],
                                "integration": {
                                    "url": f"{config.application.impulse_address}/app",
                                    "context": {
                                        "action": "status"
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
        }
    }
    return payload


def mattermost_get_update_payload(channel_id, thread_id, body, header, status_icons, status, chain_enabled,
                                  status_enabled):
    config = get_config()
    payload = {
        'channel_id': channel_id,
        'id': thread_id,
        'message': f'{status_icons} {header}',
        'props': {
            'attachments': [
                {
                    'fallback': 'test',
                    'text': body,
                    'color': status_colors.get(status),
                    'actions': [
                        {
                            "id": "chain",
                            "type": "button",
                            "name": chain_attrs(chain_enabled, status)[0],
                            "style": chain_attrs(chain_enabled, status)[1],
                            "integration": {
                                "url": f"{config.application.impulse_address}/app",
                                "context": {
                                    "action": "chain"
                                }
                            }
                        },
                        {
                            "id": "status",
                            "type": "button",
                            "name": buttons['status']['enabled']['text'] if status_enabled else
                            buttons['status']['disabled']['text'],
                            "style": buttons['status']['enabled']['style'] if status_enabled else
                            buttons['status']['disabled']['style'],
                            "integration": {
                                "url": f"{config.application.impulse_address}/app",
                                "context": {
                                    "action": "status"
                                }
                            }
                        }
                    ]
                }
            ]
        }
    }
    return payload


def mattermost_get_create_thread_payload(channel_id, body, header, status_icons, status):
    config = get_config()
    payload = {
        'channel_id': channel_id,
        'message': f'{status_icons} {header}',
        'props': {
            'attachments': [
                {
                    'fallback': 'test',
                    'text': body,
                    'color': status_colors.get(status),
                    'actions': [
                        {
                            "id": "chain",
                            "type": "button",
                            "name": buttons['chain']['takeit']['text'],
                            "style": buttons['chain']['takeit']['style'],
                            "integration": {
                                "url": f"{config.application.impulse_address}/app",
                                "context": {
                                    "action": "chain"
                                }
                            }
                        },
                        {
                            "id": "status",
                            "type": "button",
                            "name": buttons['status']['enabled']['text'],
                            "style": buttons['status']['enabled']['style'],
                            "integration": {
                                "url": f"{config.application.impulse_address}/app",
                                "context": {
                                    "action": "status"
                                }
                            }
                        }
                    ]
                }
            ]
        }
    }
    return payload
