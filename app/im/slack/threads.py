from app.config.config import get_config
from app.config.environment import get_environment_config
from app.im.colors import status_colors
from app.im.slack.buttons import chain_attrs
from app.im.slack.config import buttons
from app.time import format_freeze_expiration


def build_slack_actions(incident):
    env_config = get_environment_config()
    config = get_config()
    chain_text, chain_style = chain_attrs(incident.chain_enabled, incident.status)
    if incident.frozen_by_inhibition:
        chain_style = 'normal'
    
    actions = [
        {
            "name": 'chain',
            "type": 'button',
            "text": chain_text,
            "style": chain_style,
        }
    ]
    
    if incident.frozen_by_inhibition:
        # Frozen by inhibition - show static button (no unfreeze option)
        actions.append({
            "name": 'freeze',
            "type": 'button',
            "text": buttons['freeze']['inhibited']['text'],
            "style": buttons['freeze']['inhibited']['style'],
        })
    elif incident.frozen_until:
        freeze_text = format_freeze_expiration(incident.frozen_until, tz_str='UTC') #!
        actions.append({
            "name": 'freeze',
            "type": 'button',
            "text": freeze_text,
            "style": 'primary',
        })
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
    
    if config.app.task_management and env_config.task_management_enabled and not incident.task_link:
        actions.append({
            "name": "task",
            "text": buttons['task']['create']['text'],
            "type": "button",
            "style": buttons['task']['create']['style']
        })
    
    return actions


def slack_get_update_payload(incident, body, header, status_icons):
    actions = build_slack_actions(incident)
    display_status = 'frozen' if incident.is_frozen() else incident.status
    
    payload = {
        'channel': incident.channel_id,
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
        'ts': incident.ts,
    }
    return payload


def get_incident_message_payload(incident, body, header, status_icons):
    actions = build_slack_actions(incident)
    display_status = 'frozen' if incident.is_frozen() else incident.status
    
    payload = {
        'channel': incident.channel_id,
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
                'callback_id': 'buttons',
                'actions': actions
            }
        ]
    }
    return payload
