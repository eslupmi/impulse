from app.im.colors import status_colors
from app.im.mattermost.config import buttons
from app.config.config import get_config
from app.config.environment import get_environment_config


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


def build_mattermost_actions(chain_enabled, status, status_enabled, task_link=''):
    """
    Build the action buttons list for Mattermost messages.
    
    Args:
        chain_enabled: Whether the chain button is enabled
        status: Current incident status
        status_enabled: Whether the status button is enabled
        task_link: Optional Jira task link (if task exists)
        
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
        },
        {
            "id": "status",
            "type": "button",
            "name": buttons['status']['enabled']['text'] if status_enabled else
            buttons['status']['disabled']['text'],
            "style": buttons['status']['enabled']['style'] if status_enabled else
            buttons['status']['disabled']['style'],
            "integration": {
                "url": f"{config.messenger.impulse_address}/app",
                "context": {
                    "action": "status"
                }
            }
        }
    ]
    
    # Add Jira button if Jira is enabled
    if env_config.task_management_enabled:
        if task_link:
            # If task exists, button opens the link
            actions.append({
                "id": "file_ticket",
                "type": "button",
                "name": buttons['file_ticket']['open']['text'],
                "style": buttons['file_ticket']['open']['style'],
                "url": task_link
            })
        else:
            # If no task, button creates one
            actions.append({
                "id": "file_ticket",
                "type": "button",
                "name": buttons['file_ticket']['create']['text'],
                "style": buttons['file_ticket']['create']['style'],
                "integration": {
                    "url": f"{config.messenger.impulse_address}/app",
                    "context": {
                        "action": "file_ticket"
                    }
                }
            })
    
    return actions


def mattermost_get_button_update_payload(body, header, status_icons, status, chain_enabled, status_enabled, task_link=''):
    actions = build_mattermost_actions(chain_enabled, status, status_enabled, task_link)
    
    payload = {
        'update': {
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
    }
    return payload


def mattermost_get_update_payload(channel_id, thread_id, body, header, status_icons, status, chain_enabled,
                                  status_enabled, task_link=''):
    actions = build_mattermost_actions(chain_enabled, status, status_enabled, task_link)
    
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
                    'actions': actions
                }
            ]
        }
    }
    return payload


def mattermost_get_create_thread_payload(channel_id, body, header, status_icons, status):
    # New threads always have chain enabled and status enabled, no task link yet
    actions = build_mattermost_actions(chain_enabled=True, status=status, status_enabled=True, task_link='')
    
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
