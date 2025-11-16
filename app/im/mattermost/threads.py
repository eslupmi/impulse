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


def mattermost_get_button_update_payload(body, header, status_icons, status, chain_enabled, status_enabled, task_link=''):
    from app.config.environment import get_environment_config
    config = get_config()
    env_config = get_environment_config()
    
    actions = [
        {
            "id": "chain",
            "type": "button",
            "name": chain_attrs(chain_enabled, status)[0],
            "style": chain_attrs(chain_enabled, status)[1],
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
    if env_config.jira_enabled:
        if task_link:
            # If task exists, button opens the link
            actions.append({
                "id": "jira",
                "type": "button",
                "name": buttons['jira']['open']['text'],
                "style": buttons['jira']['open']['style'],
                "url": task_link
            })
        else:
            # If no task, button creates one
            actions.append({
                "id": "jira",
                "type": "button",
                "name": buttons['jira']['create']['text'],
                "style": buttons['jira']['create']['style'],
                "integration": {
                    "url": f"{config.messenger.impulse_address}/app",
                    "context": {
                        "action": "jira"
                    }
                }
            })
    
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
    from app.config.environment import get_environment_config
    config = get_config()
    env_config = get_environment_config()
    
    actions = [
        {
            "id": "chain",
            "type": "button",
            "name": chain_attrs(chain_enabled, status)[0],
            "style": chain_attrs(chain_enabled, status)[1],
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
    if env_config.jira_enabled:
        if task_link:
            # If task exists, button opens the link
            actions.append({
                "id": "jira",
                "type": "button",
                "name": buttons['jira']['open']['text'],
                "style": buttons['jira']['open']['style'],
                "url": task_link
            })
        else:
            # If no task, button creates one
            actions.append({
                "id": "jira",
                "type": "button",
                "name": buttons['jira']['create']['text'],
                "style": buttons['jira']['create']['style'],
                "integration": {
                    "url": f"{config.messenger.impulse_address}/app",
                    "context": {
                        "action": "jira"
                    }
                }
            })
    
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
    from app.config.environment import get_environment_config
    config = get_config()
    env_config = get_environment_config()
    
    actions = [
        {
            "id": "chain",
            "type": "button",
            "name": buttons['chain']['takeit']['text'],
            "style": buttons['chain']['takeit']['style'],
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
            "name": buttons['status']['enabled']['text'],
            "style": buttons['status']['enabled']['style'],
            "integration": {
                "url": f"{config.messenger.impulse_address}/app",
                "context": {
                    "action": "status"
                }
            }
        }
    ]
    
    # Add Jira button if Jira is enabled
    if env_config.jira_enabled:
        actions.append({
            "id": "jira",
            "type": "button",
            "name": buttons['jira']['create']['text'],
            "style": buttons['jira']['create']['style'],
            "integration": {
                "url": f"{config.messenger.impulse_address}/app",
                "context": {
                    "action": "jira"
                }
            }
        })
    
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
