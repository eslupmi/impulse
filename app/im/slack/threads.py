from app.im.colors import status_colors
from app.im.slack.buttons import chain_attrs
from app.im.slack.config import buttons
from app.config.environment import get_environment_config
from app.config.config import get_config
from app.time import format_freeze_expiration


def build_slack_actions(chain_enabled, status, frozen_until=None, task_link=''):
    """
    Build the action buttons list for Slack messages.
    
    Args:
        chain_enabled: Whether the chain button is enabled
        status: Current incident status
        frozen_until: Datetime when freeze expires (None if not frozen)
        task_link: Optional task link (if task exists)
        
    Returns:
        List of action button configurations
    """
    env_config = get_environment_config()
    config = get_config()
    chain_text, chain_style = chain_attrs(chain_enabled, status)
    
    actions = [
        {
            "name": 'chain',
            "type": 'button',
            "text": chain_text,
            "style": chain_style,
        }
    ]
    
    if frozen_until:
        freeze_text = f"Frozen until {format_freeze_expiration(frozen_until)}"
    else:
        freeze_text = buttons['freeze']['inactive']['text']
    
    freeze_options = [
        {"text": opt['text'], "value": opt['value']}
        for opt in buttons['freeze']['options']
    ]
    
    actions.append({
        "name": 'freeze',
        "type": 'select',
        "text": freeze_text,
        "style": buttons['freeze']['inactive']['style'],
        "options": freeze_options
    })
    
    if config.app.task_management and env_config.task_management_enabled and not task_link:
        actions.append({
            "name": "task",
            "text": buttons['task']['create']['text'],
            "type": "button",
            "style": buttons['task']['create']['style']
        })
    
    return actions


def slack_get_update_payload(channel_id, ts, body, header, status_icons, status, chain_enabled=True,
                             frozen_until=None, task_link=''):
    actions = build_slack_actions(chain_enabled, status, frozen_until, task_link)
    display_status = 'frozen' if frozen_until else status
    
    payload = {
        'channel': channel_id,
        'text': f'{status_icons} {header}',
        'attachments': [
            {
                'color': status_colors.get(display_status),
                'text': body,
                'mrkdwn_in': ['text'],
            },
            {
                'color': status_colors.get(display_status),
                'text': '',
                "callback_id": "buttons",
                "actions": actions,
            },
        ],
        'ts': ts,
    }
    return payload


def slack_get_create_thread_payload(channel_id, body, header, status_icons, status):
    actions = build_slack_actions(chain_enabled=True, status=status, frozen_until=None, task_link='')
    
    payload = {
        'channel': channel_id,
        'text': f'{status_icons} {header}',
        'attachments': [
            {
                'color': status_colors.get(status),
                'text': body,
                'mrkdwn_in': ['text'],
            },
            {
                'color': status_colors.get(status),
                'text': '',
                'callback_id': 'buttons',
                'actions': actions
            }
        ]
    }
    return payload
