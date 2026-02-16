from app.config.config import get_config
from app.config.environment import get_environment_config
from app.im.colors import status_colors
from app.im.mattermost.config import buttons
from app.time import format_freeze_expiration


def _chain_attrs(chain_enabled, status):
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


def _build_mattermost_actions(incident, user_timezone='UTC'):
    config = get_config()
    env_config = get_environment_config()
    
    chain_text, chain_style = _chain_attrs(incident.chain_enabled, incident.status)
    if incident.frozen_by_inhibition:
        chain_style = 'default'
    
    actions = [{
        "id": "chain",
        "type": "button",
        "name": chain_text,
        "style": chain_style,
        "integration": {
            "url": f"{config.messenger.impulse_address}/app",
            "context": {
                "action": "chain"
            }
        }
    }]
    
    if incident.frozen_by_inhibition:
        actions.append({
            "id": "freeze",
            "type": "button",
            "name": buttons['freeze']['inhibited']['text'],
            "style": buttons['freeze']['inhibited']['style'],
            "integration": {
                "url": f"{config.messenger.impulse_address}/app",
                "context": {
                    "action": "noop"
                }
            }
        })
    elif incident.frozen_until:
        freeze_text = format_freeze_expiration(incident.frozen_until, user_timezone)
        actions.append({
            "id": "freeze",
            "type": "button",
            "name": freeze_text,
            "style": buttons['freeze']['inactive']['style'],
            "integration": {
                "url": f"{config.messenger.impulse_address}/app",
                "context": {
                    "action": "unfreeze"
                }
            }
        })
    else:
        freeze_text = buttons['freeze']['inactive']['text']
        freeze_options = [
            {"text": opt['text'], "value": f"freeze_{opt['value']}"} 
            for opt in buttons['freeze']['options']
        ]
        
        actions.append({
            "id": "freeze",
            "type": "select",
            "name": freeze_text,
            "style": buttons['freeze']['inactive']['style'],
            "integration": {
                "url": f"{config.messenger.impulse_address}/app",
                "context": {}
            },
            "options": freeze_options
        })
    
    if config.app.task_management and env_config.task_management_enabled and not incident.task_link:
        actions.append({
            "id": "task",
            "type": "button",
            "name": buttons['task']['create']['text'],
            "style": buttons['task']['create']['style'],
            "integration": {
                "url": f"{config.messenger.impulse_address}/app",
                "context": {
                    "action": "task"
                }
            }
        })
    
    return actions


def mattermost_get_button_update_payload(incident, body, header, status_icons, user_timezone='UTC'):
    actions = _build_mattermost_actions(incident, user_timezone)
    display_status = 'frozen' if incident.is_frozen() else incident.status
    
    payload = {
        'update': {
            'message': f'{status_icons} {header}',
            'props': {
                'attachments': [
                    {
                        'fallback': 'test',
                        'text': body,
                        'color': status_colors.get(display_status),
                        'actions': actions
                    }
                ]
            }
        }
    }
    return payload

def mattermost_get_update_payload(incident, body, header, status_icons, tz_str):
    actions = _build_mattermost_actions(incident, tz_str)
    display_status = 'frozen' if (incident.frozen_until or incident.frozen_by_inhibition) else incident.status
    
    payload = {
        'channel_id': incident.channel_id,
        'id': incident.ts,
        'message': f'{status_icons} {header}',
        'props': {
            'attachments': [
                {
                    'fallback': 'test',
                    'text': body,
                    'color': status_colors.get(display_status),
                    'actions': actions
                }
            ]
        }
    }
    return payload


def mattermost_get_create_thread_payload(incident, body, header, status_icons):
    actions = _build_mattermost_actions(incident)
    display_status = 'frozen' if incident.frozen_by_inhibition else incident.status
    
    payload = {
        'channel_id': incident.channel_id,
        'message': f'{status_icons} {header}',
        'props': {
            'attachments': [
                {
                    'fallback': 'test',
                    'text': body,
                    'color': status_colors.get(display_status),
                    'actions': actions
                }
            ]
        }
    }
    return payload
