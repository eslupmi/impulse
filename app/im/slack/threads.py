from app.im.colors import status_colors
from app.im.slack.buttons import chain_attrs
from app.im.slack.config import buttons
from app.config.environment import get_environment_config
from app.config.config import get_config


def build_slack_actions(chain_enabled, status, status_enabled, task_link=''):
    """
    Build the action buttons list for Slack messages.
    
    Args:
        chain_enabled: Whether the chain button is enabled
        status: Current incident status
        status_enabled: Whether the status button is enabled
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
        },
        {
            "name": 'status',
            "type": 'button',
            "text": buttons['status']['enabled']['text'] if status_enabled else
            buttons['status']['disabled']['text'],
            "style": buttons['status']['enabled']['style'] if status_enabled else
            buttons['status']['disabled']['style'],
        }
    ]
    
    if config.app.task_management and env_config.task_management_enabled and not task_link:
        actions.append({
            "name": "task",
            "text": buttons['task']['create']['text'],
            "type": "button",
            "style": buttons['task']['create']['style']
        })
    
    return actions


def slack_get_update_payload(channel_id, ts, body, header, status_icons, status, chain_enabled=True,
                             status_enabled=True, task_link=''):
    actions = build_slack_actions(chain_enabled, status, status_enabled, task_link)
    
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
                "callback_id": "buttons",
                "actions": actions,
            },
        ],
        'ts': ts,
    }
    return payload


def slack_get_create_thread_payload(channel_id, body, header, status_icons, status):
    # New threads always have chain enabled and status enabled, no task link yet
    actions = build_slack_actions(chain_enabled=True, status=status, status_enabled=True, task_link='')
    
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
