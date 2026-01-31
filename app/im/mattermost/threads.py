from app.config.config import get_config
from app.config.environment import get_environment_config
from app.im.colors import status_colors
from app.im.mattermost.config import buttons
from app.time import format_freeze_expiration


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


def build_mattermost_actions(chain_enabled, status, frozen_until=None, task_link='', user_timezone='UTC',
                             frozen_by_inhibition=False):
    """
    Build the action buttons list for Mattermost messages.
    
    Args:
        chain_enabled: Whether the chain button is enabled
        status: Current incident status
        frozen_until: Datetime when freeze expires (None if not frozen)
        task_link: Optional Jira task link (if task exists)
        user_timezone: User's timezone for formatting
        frozen_by_inhibition: Whether incident is frozen by inhibition rule
        
    Returns:
        List of action button configurations
    """
    config = get_config()
    env_config = get_environment_config()
    
    chain_text, chain_style = chain_attrs(chain_enabled, status)
    
    actions = [
        {
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
        }
    ]
    
    if frozen_by_inhibition:
        # Frozen by inhibition - show static button (no unfreeze option)
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
    elif frozen_until:
        freeze_text = format_freeze_expiration(frozen_until, user_timezone)
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
    
    if config.app.task_management and env_config.task_management_enabled and not task_link:
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


def mattermost_get_button_update_payload(body, header, status_icons, status, chain_enabled, frozen_until, task_link='', 
                                         user_timezone='UTC', frozen_by_inhibition=False):
    actions = build_mattermost_actions(chain_enabled, status, frozen_until, task_link, user_timezone, frozen_by_inhibition)
    display_status = 'frozen' if (frozen_until or frozen_by_inhibition) else status
    
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


def mattermost_get_update_payload(channel_id, thread_id, body, header, status_icons, status, chain_enabled,
                                  frozen_until, task_link='', frozen_by_inhibition=False):
    actions = build_mattermost_actions(chain_enabled, status, frozen_until, task_link, frozen_by_inhibition=frozen_by_inhibition)
    display_status = 'frozen' if (frozen_until or frozen_by_inhibition) else status
    
    payload = {
        'channel_id': channel_id,
        'id': thread_id,
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


def mattermost_get_create_thread_payload(channel_id, body, header, status_icons, status):
    actions = build_mattermost_actions(chain_enabled=True, status=status, frozen_until=None, task_link='')
    
    payload = {
        'channel_id': channel_id,
        'message': f'{status_icons} {header}',
        'props': {
            'attachments': [
                {
                    'fallback': 'test',
                    'text': body,
                    'color': status_colors.get(status),
                    'actions': actions
                }
            ]
        }
    }
    return payload
