from app.im.colors import status_colors
from app.im.slack.buttons import chain_attrs
from app.im.slack.config import buttons


def slack_get_update_payload(channel_id, ts, body, header, status_icons, status, chain_enabled=True,
                             status_enabled=True, task_link=''):
    from app.config.environment import get_environment_config
    env_config = get_environment_config()
    
    actions = [
        {
            "name": 'chain',
            "type": 'button',
            "text": chain_attrs(chain_enabled, status)[0],
            "style": chain_attrs(chain_enabled, status)[1],
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
    
    # Add Jira button if Jira is enabled
    if env_config.jira_enabled:
        if task_link:
            # If task exists, button opens the link
            actions.append({
                "name": "jira",
                "text": buttons['jira']['open']['text'],
                "type": "button",
                "style": buttons['jira']['open']['style'],
                "url": task_link
            })
        else:
            # If no task, button creates one
            actions.append({
                "name": "jira",
                "text": buttons['jira']['create']['text'],
                "type": "button",
                "style": buttons['jira']['create']['style']
            })
    
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
    from app.config.environment import get_environment_config
    env_config = get_environment_config()
    
    actions = [
        {
            "name": "chain",
            "text": buttons['chain']['takeit']['text'],
            "type": "button",
            "style": buttons['chain']['takeit']['style']
        },
        {
            "name": "status",
            "text": buttons['status']['enabled']['text'],
            "type": "button",
            "style": buttons['status']['enabled']['style']
        }
    ]
    
    # Add Jira button if Jira is enabled
    if env_config.jira_enabled:
        actions.append({
            "name": "jira",
            "text": buttons['jira']['create']['text'],
            "type": "button",
            "style": buttons['jira']['create']['style']
        })
    
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
